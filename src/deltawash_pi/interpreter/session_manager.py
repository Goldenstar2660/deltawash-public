"""Session gating logic for WHO Steps 2-7 compliance."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Deque, Dict, Optional
from uuid import uuid4

from deltawash_pi.config.loader import Config
from deltawash_pi.interpreter.types import FramePacket


class SessionEventType(str, Enum):
    STARTED = "session_started"
    ENDED = "session_ended"


@dataclass(frozen=True)
class SessionEvent:
    event_type: SessionEventType
    session_id: str
    timestamp_ms: int
    config_version: str
    details: Dict[str, object]


class SessionManager:
    """Evaluates FramePacket streams to emit session lifecycle events."""

    def __init__(self, config: Config, callback: Callable[[SessionEvent], None]):
        self._config = config
        self._callback = callback
        self._start_window: Deque[bool] = deque(maxlen=config.session.start_window_frames)
        self._session_active = False
        self._current_session_id: Optional[str] = None
        self._session_start_ts: Optional[int] = None
        self._last_active_ts: Optional[int] = None

    def process_frame(self, packet: FramePacket) -> None:
        gate_ok = self._meets_start_conditions(packet)
        self._start_window.append(gate_ok)

        if not self._session_active:
            if len(self._start_window) == self._start_window.maxlen and all(self._start_window):
                self._start_session(packet.timestamp_ms)
        else:
            if gate_ok:
                self._last_active_ts = packet.timestamp_ms
            elif self._last_active_ts is not None:
                elapsed = packet.timestamp_ms - self._last_active_ts
                if elapsed >= self._config.session.stop_timeout_ms:
                    self._end_session(packet.timestamp_ms, reason="timeout")

    def reset(self) -> None:
        if self._session_active:
            self._end_session(self._last_active_ts or 0, reason="reset")
        self._start_window.clear()

    @property
    def session_active(self) -> bool:
        return self._session_active

    @property
    def current_session_id(self) -> Optional[str]:
        return self._current_session_id

    def _start_session(self, timestamp_ms: int) -> None:
        self._session_active = True
        self._current_session_id = str(uuid4())
        self._session_start_ts = timestamp_ms
        self._last_active_ts = timestamp_ms
        self._emit(SessionEvent(
            event_type=SessionEventType.STARTED,
            session_id=self._current_session_id,
            timestamp_ms=timestamp_ms,
            config_version=self._config.config_version,
            details={"roi": {
                "x": self._config.roi.x,
                "y": self._config.roi.y,
                "width": self._config.roi.width,
                "height": self._config.roi.height,
            }},
        ))

    def _end_session(self, timestamp_ms: int, *, reason: str) -> None:
        if not self._session_active or self._current_session_id is None or self._session_start_ts is None:
            return
        duration = max(0, timestamp_ms - self._session_start_ts)
        self._emit(SessionEvent(
            event_type=SessionEventType.ENDED,
            session_id=self._current_session_id,
            timestamp_ms=timestamp_ms,
            config_version=self._config.config_version,
            details={
                "reason": reason,
                "duration_ms": duration,
            },
        ))
        self._session_active = False
        self._current_session_id = None
        self._session_start_ts = None
        self._last_active_ts = None
        self._start_window.clear()

    def _emit(self, event: SessionEvent) -> None:
        self._callback(event)

    def _meets_start_conditions(self, packet: FramePacket) -> bool:
        hands_total = self._extract_int(packet, "hand_count", default=0)
        if hands_total < self._config.session.min_hands:
            return False
        hands_in_roi = self._extract_int(packet, "hands_in_roi", default=hands_total)
        if hands_in_roi < self._config.session.min_hands:
            return False
        if self._config.session.require_motion:
            motion = packet.motion
            if motion.mean_velocity < self._config.session.motion_threshold:
                return False
            if motion.relative_motion < self._config.session.relative_motion_threshold:
                return False
        return True

    @staticmethod
    def _extract_int(packet: FramePacket, key: str, *, default: int = 0) -> int:
        value = packet.metadata.get(key, default)
        if isinstance(value, int):
            return value
        return default


__all__ = [
    "SessionEvent",
    "SessionEventType",
    "SessionManager",
]
