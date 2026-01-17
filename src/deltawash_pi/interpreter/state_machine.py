"""Interpreter state machine for per-step timing and uncertainty handling."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable, Dict, List, Optional, Protocol, Sequence, Tuple

from deltawash_pi.config.loader import Config, StepThreshold, VALID_STEP_IDS
from deltawash_pi.interpreter.types import (
    LedSignalState,
    StepID,
    StepOrientation,
    StepSignal,
    StepState,
    StepStatus,
    UncertaintyEvent,
    UncertaintyReason,
)


class InterpreterEventType(str, Enum):
    STEP_STATE = "step_state_update"
    ACTIVE_STEP = "active_step_changed"
    UNCERTAINTY = "uncertainty_event"


@dataclass(frozen=True)
class InterpreterEvent:
    event_type: InterpreterEventType
    session_id: str
    timestamp_ms: int
    step_id: Optional[StepID]
    state: Optional[StepState]
    details: Dict[str, object]


class LedPublisher(Protocol):
    def start_session(self, session_id: str) -> None:
        ...

    def end_session(self) -> None:
        ...

    def publish(self, step_id: StepID, state: LedSignalState, timestamp_ms: int) -> bool:
        ...


class InterpreterStateMachine:
    """Accumulates confident dwell time per step and emits state events."""

    def __init__(
        self,
        config: Config,
        callback: Optional[Callable[[InterpreterEvent], None]] = None,
        *,
        led_client: Optional[LedPublisher] = None,
    ) -> None:
        self._callback = callback or (lambda event: None)
        self._step_thresholds = self._build_thresholds(config)
        self._step_order = list(self._step_thresholds.keys())
        self._session_id: Optional[str] = None
        self._step_statuses: Dict[StepID, StepStatus] = {}
        self._last_confident_ts: Dict[StepID, Optional[int]] = {}
        self._last_published: Dict[StepID, Tuple[StepState, int, StepOrientation]] = {}
        self._uncertainty_events: List[UncertaintyEvent] = []
        self._active_step_id: Optional[StepID] = None
        self._led_client = led_client
        self._led_states: Dict[StepID, LedSignalState] = {}

    def start_session(self, session_id: str, timestamp_ms: int) -> None:
        """Reset interpreter state for a new session."""

        self._session_id = session_id
        self._uncertainty_events.clear()
        self._step_statuses = {step: StepStatus(step_id=step) for step in self._step_order}
        self._last_confident_ts = {step: None for step in self._step_order}
        self._last_published = {
            step: (StepState.NOT_STARTED, 0, StepOrientation.NONE) for step in self._step_order
        }
        self._active_step_id = None
        self._led_states = {}
        self._begin_led_session(timestamp_ms)
        self._publish_all(timestamp_ms, force=True)
        self._emit_active_step(timestamp_ms)

    def end_session(self, timestamp_ms: int) -> None:
        """Finalize current session and clear active markers."""

        if not self._session_id:
            return
        self._set_active_step(None, timestamp_ms)
        self._end_led_session(timestamp_ms)
        if self._led_client:
            self._led_client.end_session()
        self._session_id = None

    def process_signals(self, signals: Sequence[StepSignal], timestamp_ms: int) -> None:
        """Consume detector outputs for the current frame/window."""

        if not self._session_id:
            return
        signal_list = list(signals or [])
        active_signal = self._select_active_signal(signal_list)
        self._set_active_step(active_signal.step_id if active_signal else None, timestamp_ms)
        signal_map = {sig.step_id: sig for sig in signal_list}
        for step_id in self._step_order:
            status = self._step_statuses[step_id]
            threshold = self._step_thresholds[step_id]
            signal = signal_map.get(step_id)
            self._update_step(status, threshold, signal, timestamp_ms)

    def record_uncertainty(
        self,
        reason: UncertaintyReason,
        timestamp_ms: int,
        *,
        details: Optional[str] = None,
    ) -> None:
        """Record an uncertainty event originating outside detector confidence."""

        if not self._session_id:
            return
        event = UncertaintyEvent(timestamp_ms=timestamp_ms, reason=reason, details=details)
        self._uncertainty_events.append(event)
        payload: Dict[str, object] = {"reason": reason.value}
        if details:
            payload["details"] = details
        self._emit_event(InterpreterEventType.UNCERTAINTY, timestamp_ms, None, None, payload)

    @property
    def active_step_id(self) -> Optional[StepID]:
        return self._active_step_id

    def snapshot(self) -> List[StepStatus]:
        if not self._step_statuses:
            return []
        return [replace(status) for status in self._step_statuses.values()]

    def uncertainty_events(self) -> List[UncertaintyEvent]:
        return list(self._uncertainty_events)

    def _update_step(
        self,
        status: StepStatus,
        threshold: StepThreshold,
        signal: Optional[StepSignal],
        timestamp_ms: int,
    ) -> None:
        if status.state is StepState.COMPLETED:
            return

        before_state = status.state
        before_ms = status.accumulated_ms
        before_orientation = status.orientation

        if signal and signal.is_confident:
            if signal.orientation is not StepOrientation.NONE:
                status.orientation = signal.orientation
            if status.state in (StepState.NOT_STARTED, StepState.UNCERTAIN):
                status.state = StepState.IN_PROGRESS
            last_ts = self._last_confident_ts.get(status.step_id)
            current_ts = signal.timestamp_ms
            if last_ts is not None:
                delta = max(0, current_ts - last_ts)
                if delta > 0:
                    status.accumulated_ms += delta
            self._last_confident_ts[status.step_id] = current_ts
            if status.accumulated_ms >= threshold.duration_ms and status.state is not StepState.COMPLETED:
                status.state = StepState.COMPLETED
                status.completed_ts = current_ts
                self._last_confident_ts[status.step_id] = None
        else:
            self._last_confident_ts[status.step_id] = None
            if status.state is StepState.IN_PROGRESS:
                status.state = StepState.UNCERTAIN
                status.uncertainty_count += 1
                self.record_uncertainty(
                    UncertaintyReason.LOW_CONFIDENCE,
                    timestamp_ms,
                    details=f"step={status.step_id.value}",
                )

        changed = (
            status.state != before_state
            or status.accumulated_ms != before_ms
            or status.orientation != before_orientation
        )
        if changed:
            self._publish_status(status, timestamp_ms)

    def _publish_status(self, status: StepStatus, timestamp_ms: int, *, force: bool = False) -> None:
        if not self._session_id:
            return
        key = (status.state, status.accumulated_ms, status.orientation)
        if not force and self._last_published.get(status.step_id) == key:
            return
        self._last_published[status.step_id] = key
        threshold = self._step_thresholds[status.step_id]
        details: Dict[str, object] = {
            "accumulated_ms": status.accumulated_ms,
            "orientation": status.orientation.value,
            "completed_ts": status.completed_ts,
            "uncertainty_count": status.uncertainty_count,
            "duration_ms": threshold.duration_ms,
            "is_current": status.step_id == self._active_step_id,
        }
        self._emit_event(InterpreterEventType.STEP_STATE, timestamp_ms, status.step_id, status.state, details)
        if status.state is StepState.COMPLETED:
            self._send_led_signal(status.step_id, LedSignalState.COMPLETED, timestamp_ms)

    def _publish_all(self, timestamp_ms: int, *, force: bool = False) -> None:
        for status in self._step_statuses.values():
            self._publish_status(status, timestamp_ms, force=force)

    def _select_active_signal(self, signals: Sequence[StepSignal]) -> Optional[StepSignal]:
        confident = [sig for sig in signals if sig.is_confident]
        if not confident:
            return None
        return max(confident, key=lambda sig: sig.confidence)

    def _set_active_step(self, step_id: Optional[StepID], timestamp_ms: int) -> None:
        if self._active_step_id is step_id:
            return
        previous = self._active_step_id
        self._active_step_id = step_id
        self._emit_active_step(timestamp_ms, previous_step=previous)

    def _emit_active_step(self, timestamp_ms: int, *, previous_step: Optional[StepID] = None) -> None:
        if not self._session_id:
            return
        details: Dict[str, object] = {
            "active_step": self._active_step_id.value if self._active_step_id else None,
        }
        self._emit_event(InterpreterEventType.ACTIVE_STEP, timestamp_ms, self._active_step_id, None, details)
        self._sync_led_active(previous_step, self._active_step_id, timestamp_ms)

    def _emit_event(
        self,
        event_type: InterpreterEventType,
        timestamp_ms: int,
        step_id: Optional[StepID],
        state: Optional[StepState],
        details: Dict[str, object],
    ) -> None:
        if not self._session_id:
            return
        event = InterpreterEvent(
            event_type=event_type,
            session_id=self._session_id,
            timestamp_ms=timestamp_ms,
            step_id=step_id,
            state=state,
            details=dict(details),
        )
        self._callback(event)

    def _begin_led_session(self, timestamp_ms: int) -> None:
        if not self._led_client or not self._session_id:
            return
        self._led_client.start_session(self._session_id)

    def _end_led_session(self, timestamp_ms: int) -> None:
        if not self._led_client:
            return
        for step in self._step_order:
            self._send_led_signal(step, LedSignalState.IDLE, timestamp_ms, force=True)
        self._led_states.clear()

    def _sync_led_active(
        self,
        previous_step: Optional[StepID],
        current_step: Optional[StepID],
        timestamp_ms: int,
    ) -> None:
        if not self._led_client:
            return
        
        # IMPORTANT: Turn off the previous step's LED first (unless it's completed)
        if previous_step and previous_step in self._step_statuses:
            previous_status = self._step_statuses[previous_step]
            if previous_status.state is not StepState.COMPLETED:
                # Previous step was blinking (CURRENT) but is no longer active - turn it off
                self._send_led_signal(previous_step, LedSignalState.IDLE, timestamp_ms, force=True)
        
        # Now set the current step's LED
        if current_step and current_step in self._step_statuses:
            current_status = self._step_statuses[current_step]
            desired = (
                LedSignalState.COMPLETED
                if current_status.state is StepState.COMPLETED
                else LedSignalState.CURRENT
            )
            self._send_led_signal(current_step, desired, timestamp_ms)

    def _send_led_signal(
        self,
        step_id: StepID,
        state: LedSignalState,
        timestamp_ms: int,
        *,
        force: bool = False,
    ) -> None:
        if not self._led_client:
            return
        if not force and self._led_states.get(step_id) is state:
            return
        delivered = self._led_client.publish(step_id, state, timestamp_ms)
        if delivered:
            self._led_states[step_id] = state

    @staticmethod
    def _build_thresholds(config: Config) -> Dict[StepID, StepThreshold]:
        thresholds: Dict[StepID, StepThreshold] = {}
        for step in VALID_STEP_IDS:
            if step not in config.steps:
                continue
            thresholds[StepID(step)] = config.steps[step]
        return thresholds


__all__ = [
    "InterpreterEvent",
    "InterpreterEventType",
    "InterpreterStateMachine",
]
