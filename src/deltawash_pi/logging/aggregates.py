"""Analytics helpers for summarizing session logs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from deltawash_pi.interpreter.types import StepID

LOGGER = logging.getLogger(__name__)
_STATS_VERSION = "1.0.0"


@dataclass(frozen=True)
class AggregateSummary:
    stats_version: str
    generated_ts: str
    sessions_count: int
    most_missed_step: Optional[str]
    average_step_times_ms: Dict[str, float]
    uncertainty_frequency: Dict[str, int]
    fallback_frequency: Dict[str, int]
    model_usage_rate: float
    avg_model_confidence: Optional[float]
    avg_inference_time_ms: Optional[float]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def load_session_records(log_dir: Path) -> List[Dict[str, object]]:
    if not log_dir.exists():
        LOGGER.warning("Log directory %s not found; returning empty summary", log_dir)
        return []
    records: List[Dict[str, object]] = []
    for path in sorted(log_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    LOGGER.warning("Skipping invalid log line in %s: %s", path, exc)
    return records


def summarize_records(records: Iterable[Dict[str, object]]) -> AggregateSummary:
    entries = list(records)
    sessions_count = len(entries)
    step_totals: Dict[str, int] = {step.value: 0 for step in StepID}
    step_counts: Dict[str, int] = {step.value: 0 for step in StepID}
    step_incomplete: Dict[str, int] = {step.value: 0 for step in StepID}
    uncertainty_frequency: Dict[str, int] = {}
    fallback_frequency: Dict[str, int] = {}
    total_model = 0
    total_fallback = 0
    total_conf_sum = 0.0
    total_conf_samples = 0
    total_latency_sum = 0.0
    total_latency_samples = 0

    for record in entries:
        for status in record.get("step_statuses", []):
            step_id = str(status.get("step_id"))
            accumulated = status.get("accumulated_ms")
            state = status.get("state")
            if isinstance(step_id, str) and step_id in step_totals:
                if isinstance(accumulated, (int, float)):
                    step_totals[step_id] += int(accumulated)
                step_counts[step_id] += 1
                if state != "COMPLETED":
                    step_incomplete[step_id] += 1
        for uncertainty in record.get("uncertainty_events", []):
            reason = uncertainty.get("reason")
            if isinstance(reason, str):
                uncertainty_frequency[reason] = uncertainty_frequency.get(reason, 0) + 1
        for fallback in record.get("fallback_events", []):
            reason = fallback.get("reason")
            if isinstance(reason, str):
                fallback_frequency[reason] = fallback_frequency.get(reason, 0) + 1
        total_model += int(record.get("model_inference_count", 0) or 0)
        total_fallback += int(record.get("heuristic_fallback_count", 0) or 0)

        conf_samples = int(record.get("model_confidence_samples", 0) or 0)
        conf_sum = record.get("model_confidence_sum")
        if conf_sum is None and conf_samples > 0:
            avg_conf = record.get("avg_model_confidence")
            if isinstance(avg_conf, (int, float)):
                conf_sum = float(avg_conf) * conf_samples
        if isinstance(conf_sum, (int, float)) and conf_samples > 0:
            total_conf_sum += float(conf_sum)
            total_conf_samples += conf_samples

        latency_samples = int(record.get("inference_time_samples", 0) or 0)
        latency_sum = record.get("inference_time_sum_ms")
        if latency_sum is None and latency_samples > 0:
            avg_latency = record.get("avg_inference_time_ms")
            if isinstance(avg_latency, (int, float)):
                latency_sum = float(avg_latency) * latency_samples
        if isinstance(latency_sum, (int, float)) and latency_samples > 0:
            total_latency_sum += float(latency_sum)
            total_latency_samples += latency_samples

    average_step_times = _average_map(step_totals, step_counts)
    most_missed_step = _select_most_missed(step_incomplete, step_counts)
    model_usage_rate = 0.0
    total_classifications = total_model + total_fallback
    if total_classifications > 0:
        model_usage_rate = total_model / total_classifications

    avg_confidence = None
    if total_conf_samples > 0:
        avg_confidence = total_conf_sum / total_conf_samples

    avg_latency = None
    if total_latency_samples > 0:
        avg_latency = total_latency_sum / total_latency_samples

    summary = AggregateSummary(
        stats_version=_STATS_VERSION,
        generated_ts=_now_iso(),
        sessions_count=sessions_count,
        most_missed_step=most_missed_step,
        average_step_times_ms=average_step_times,
        uncertainty_frequency=dict(sorted(uncertainty_frequency.items())),
        fallback_frequency=dict(sorted(fallback_frequency.items())),
        model_usage_rate=model_usage_rate,
        avg_model_confidence=avg_confidence,
        avg_inference_time_ms=avg_latency,
    )
    return summary


def persist_summary(
    summary: AggregateSummary,
    *,
    out_path: Path,
    preserve_accuracy: bool = True,
) -> None:
    payload = summary.to_dict()
    if preserve_accuracy and out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            accuracy = existing.get("accuracy")
            if isinstance(accuracy, dict):
                payload["accuracy"] = accuracy
        except json.JSONDecodeError:
            LOGGER.warning("Existing summary file %s is invalid; overwriting", out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def merge_accuracy(out_path: Path, accuracy_section: Dict[str, object]) -> None:
    base: Dict[str, object] = {}
    if out_path.exists():
        try:
            base = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            LOGGER.warning("Existing summary file %s is invalid; recreating", out_path)
    base["accuracy"] = accuracy_section
    if "stats_version" not in base:
        base["stats_version"] = _STATS_VERSION
    if "generated_ts" not in base:
        base["generated_ts"] = _now_iso()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(base, indent=2), encoding="utf-8")


def _average_map(totals: Dict[str, int], counts: Dict[str, int]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for key, total in totals.items():
        count = counts.get(key, 0)
        if count <= 0:
            continue
        result[key] = round(total / count, 2)
    return result


def _select_most_missed(incomplete: Dict[str, int], counts: Dict[str, int]) -> Optional[str]:
    candidate = None
    candidate_ratio = -1.0
    for step_id, missed in incomplete.items():
        total = counts.get(step_id, 0)
        if total <= 0:
            continue
        ratio = missed / total
        if ratio > candidate_ratio:
            candidate_ratio = ratio
            candidate = step_id
    return candidate


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "AggregateSummary",
    "load_session_records",
    "merge_accuracy",
    "persist_summary",
    "summarize_records",
]
