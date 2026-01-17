"""Structured session logging utilities for WHO steps 2-7."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from deltawash_pi.config.loader import ROI
from deltawash_pi.interpreter.session_manager import SessionEvent
from deltawash_pi.interpreter.types import (
    StepID,
    StepSignal,
    StepSignalSource,
    StepStatus,
    UncertaintyEvent,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class FallbackEvent:
    """Represents a single fallback occurrence during a session."""

    timestamp_ms: int
    reason: str
    model_confidence: Optional[float] = None
    landmark_confidence: Optional[float] = None


@dataclass
class _SignalStats:
    model_count: int = 0
    heuristic_count: int = 0
    demo_count: int = 0
    model_confidence_sum: float = 0.0

    def register(self, source: StepSignalSource, confidence: float) -> None:
        if source is StepSignalSource.MODEL:
            self.model_count += 1
            self.model_confidence_sum += confidence
        elif source is StepSignalSource.DEMO:
            self.demo_count += 1
        else:
            self.heuristic_count += 1

    def classification_source(self) -> str:
        has_model = self.model_count > 0
        has_fallback = (self.heuristic_count + self.demo_count) > 0
        if has_model and has_fallback:
            return "MIXED"
        if has_model:
            return "MODEL"
        if has_fallback:
            return "HEURISTIC"
        return "UNKNOWN"

    def avg_model_confidence(self) -> Optional[float]:
        if self.model_count <= 0:
            return None
        return self.model_confidence_sum / self.model_count


@dataclass
class _SessionState:
    session_id: str
    config_version: str
    roi: ROI
    demo_mode: bool
    demo_asset_id: Optional[str]
    model_version: Optional[str]
    start_ts_ms: int
    notes: List[str] = field(default_factory=list)
    step_stats: Dict[StepID, _SignalStats] = field(default_factory=dict)
    fallback_events: List[FallbackEvent] = field(default_factory=list)
    model_inference_count: int = 0
    heuristic_fallback_count: int = 0
    model_confidence_sum: float = 0.0
    model_confidence_samples: int = 0
    inference_latency_sum_ms: float = 0.0
    inference_latency_samples: int = 0


class SessionLogger:
    """Persists SessionRecord payloads to daily JSONL files."""

    def __init__(self, log_dir: str | Path = "logs/sessions") -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: Dict[str, _SessionState] = {}

    def handle_session_started(
        self,
        event: SessionEvent,
        *,
        roi: ROI,
        demo_mode: bool,
        demo_asset_id: Optional[str],
        model_version: Optional[str],
    ) -> None:
        LOGGER.debug("Initializing session logger for %s", event.session_id)
        self._sessions[event.session_id] = _SessionState(
            session_id=event.session_id,
            config_version=event.config_version,
            roi=roi,
            demo_mode=demo_mode,
            demo_asset_id=demo_asset_id,
            model_version=model_version,
            start_ts_ms=event.timestamp_ms,
        )

    def handle_session_ended(
        self,
        event: SessionEvent,
        *,
        step_statuses: Sequence[StepStatus],
        uncertainty_events: Sequence[UncertaintyEvent],
    ) -> None:
        state = self._sessions.pop(event.session_id, None)
        if not state:
            LOGGER.debug("No active session state for %s; skipping flush", event.session_id)
            return
        duration_note = event.details.get("duration_ms")
        reason_note = event.details.get("reason")
        if duration_note is not None:
            state.notes.append(f"duration_ms={duration_note}")
        if reason_note:
            state.notes.append(f"reason={reason_note}")
        record = self._build_record(
            state=state,
            end_ts_ms=event.timestamp_ms,
            step_statuses=step_statuses,
            uncertainty_events=uncertainty_events,
        )
        self._write_record(record, state.start_ts_ms)

    def record_step_signals(
        self,
        session_id: Optional[str],
        signals: Sequence[StepSignal],
        *,
        inference_latency_ms: Optional[float],
    ) -> None:
        if not session_id:
            return
        state = self._sessions.get(session_id)
        if not state:
            return
        saw_model_signal = False
        for signal in signals:
            stats = state.step_stats.setdefault(signal.step_id, _SignalStats())
            stats.register(signal.source, signal.confidence)
            if signal.source is StepSignalSource.MODEL:
                saw_model_signal = True
                state.model_inference_count += 1
                state.model_confidence_sum += signal.confidence
                state.model_confidence_samples += 1
            else:
                state.heuristic_fallback_count += 1
        if inference_latency_ms is not None and saw_model_signal:
            state.inference_latency_sum_ms += inference_latency_ms
            state.inference_latency_samples += 1

    def record_fallback(
        self,
        session_id: Optional[str],
        *,
        timestamp_ms: int,
        reason: str,
        model_confidence: Optional[float] = None,
        landmark_confidence: Optional[float] = None,
    ) -> None:
        if not session_id:
            return
        state = self._sessions.get(session_id)
        if not state:
            return
        state.fallback_events.append(
            FallbackEvent(
                timestamp_ms=timestamp_ms,
                reason=reason,
                model_confidence=model_confidence,
                landmark_confidence=landmark_confidence,
            )
        )

    def _build_record(
        self,
        *,
        state: _SessionState,
        end_ts_ms: int,
        step_statuses: Sequence[StepStatus],
        uncertainty_events: Sequence[UncertaintyEvent],
    ) -> Dict[str, object]:
        step_payloads: List[Dict[str, object]] = []
        total_rubbing_ms = 0
        for status in step_statuses:
            stats = state.step_stats.get(status.step_id, _SignalStats())
            total_rubbing_ms += max(0, status.accumulated_ms)
            step_payloads.append(_serialize_step_status(status, stats))

        total_classifications = state.model_inference_count + state.heuristic_fallback_count
        model_usage_rate = 0.0
        if total_classifications > 0:
            model_usage_rate = state.model_inference_count / total_classifications

        avg_model_confidence = None
        if state.model_confidence_samples > 0:
            avg_model_confidence = state.model_confidence_sum / state.model_confidence_samples

        avg_inference_latency = None
        if state.inference_latency_samples > 0:
            avg_inference_latency = (
                state.inference_latency_sum_ms / state.inference_latency_samples
            )

        record: Dict[str, object] = {
            "session_id": state.session_id,
            "config_version": state.config_version,
            "model_version": state.model_version,
            "start_ts": _ms_to_iso(state.start_ts_ms),
            "end_ts": _ms_to_iso(end_ts_ms),
            "roi_rect": _roi_to_dict(state.roi),
            "demo_mode": state.demo_mode,
            "demo_asset_id": state.demo_asset_id,
            "step_statuses": step_payloads,
            "uncertainty_events": [_serialize_uncertainty(event) for event in uncertainty_events],
            "fallback_events": [_serialize_fallback(event) for event in state.fallback_events],
            "total_rubbing_ms": total_rubbing_ms,
            "model_inference_count": state.model_inference_count,
            "heuristic_fallback_count": state.heuristic_fallback_count,
            "avg_inference_time_ms": avg_inference_latency,
            "inference_time_samples": state.inference_latency_samples,
            "inference_time_sum_ms": state.inference_latency_sum_ms,
            "avg_model_confidence": avg_model_confidence,
            "model_confidence_samples": state.model_confidence_samples,
            "model_confidence_sum": state.model_confidence_sum,
            "model_usage_rate": model_usage_rate,
            "notes": state.notes,
        }
        return record

    def _write_record(self, record: Dict[str, object], start_ts_ms: int) -> None:
        date_bucket = datetime.fromtimestamp(start_ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
        target = self._log_dir / f"{date_bucket}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, separators=(",", ":"))
        with target.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")


def detect_model_version() -> Optional[str]:
    """Best-effort hash of bundled ML weight metadata for logging."""

    try:
        import importlib

        module = importlib.import_module("deltawash_pi.ml")
        module_path = Path(module.__file__).resolve()
    except Exception:  # pylint: disable=broad-exception-caught
        return None

    weight_dir = module_path.parent
    candidates = sorted(weight_dir.glob("*.pth"))
    if not candidates:
        return None
    digest = hashlib.sha1()
    for candidate in candidates:
        try:
            stat = candidate.stat()
        except FileNotFoundError:
            continue
        payload = f"{candidate.name}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
        digest.update(payload)
    return digest.hexdigest()[:12]


def _serialize_step_status(status: StepStatus, stats: _SignalStats) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "step_id": status.step_id.value,
        "orientation": status.orientation.value,
        "state": status.state.value,
        "accumulated_ms": status.accumulated_ms,
        "completed_ts": _ms_to_iso(status.completed_ts) if status.completed_ts is not None else None,
        "uncertainty_count": status.uncertainty_count,
        "classification_source": stats.classification_source(),
    }
    model_confidence = stats.avg_model_confidence()
    if model_confidence is not None:
        payload["model_confidence_avg"] = model_confidence
    return payload


def _serialize_uncertainty(event: UncertaintyEvent) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "timestamp_ms": event.timestamp_ms,
        "reason": event.reason.value,
    }
    if event.details:
        payload["details"] = event.details
    return payload


def _serialize_fallback(event: FallbackEvent) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "timestamp_ms": event.timestamp_ms,
        "reason": event.reason,
    }
    if event.model_confidence is not None:
        payload["model_confidence"] = event.model_confidence
    if event.landmark_confidence is not None:
        payload["landmark_confidence"] = event.landmark_confidence
    return payload


def _ms_to_iso(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _roi_to_dict(roi: ROI) -> Dict[str, int]:
    return {
        "x": roi.x,
        "y": roi.y,
        "width": roi.width,
        "height": roi.height,
    }


__all__ = ["SessionLogger", "detect_model_version", "FallbackEvent"]
