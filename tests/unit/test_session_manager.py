from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from deltawash_pi.config.loader import (
    Config,
    DemoRecordingConfig,
    Esp8266Config,
    HandTrackingConfig,
    ROI,
    Resolution,
    SessionConfig,
    StepThreshold,
    VALID_STEP_IDS,
    VideoCaptureConfig,
)
from deltawash_pi.interpreter.session_manager import (
    SessionEvent,
    SessionEventType,
    SessionManager,
)
from deltawash_pi.interpreter.types import FramePacket, MotionMetrics


def _build_config(*, start_window_frames: int = 3, stop_timeout_ms: int = 500) -> Config:
    steps = {
        step_id: StepThreshold(duration_ms=3000, confidence_min=0.7, orientation_hint=None)
        for step_id in VALID_STEP_IDS
    }
    return Config(
        source=Path("test-config.yaml"),
        config_version="test-config",
        roi=ROI(x=0, y=0, width=400, height=300),
        session=SessionConfig(
            motion_threshold=0.5,
            relative_motion_threshold=0.3,
            start_window_frames=start_window_frames,
            stop_timeout_ms=stop_timeout_ms,
            min_hands=2,
            require_motion=True,
        ),
        steps=steps,
        esp8266=Esp8266Config(enabled=False, endpoint=None, timeout_ms=500, blink_hz=1.0),
        video_capture=VideoCaptureConfig(enabled=False, storage_path=None, retention_seconds=None, max_sessions=None),
        demo_recording=DemoRecordingConfig(enabled=False, output_path=None),
        resolution=Resolution(width=640, height=480),
        hand_tracking=HandTrackingConfig(
            max_num_hands=2,
            model_complexity=1,
            min_detection_confidence=0.3,
            min_tracking_confidence=0.3,
            smoothing_window=1,
        ),
    )


def _packet(
    *,
    timestamp_ms: int,
    mean_velocity: float,
    relative_motion: float,
    hand_count: int = 2,
    hands_in_roi: int | None = None,
) -> FramePacket:
    metadata = {
        "hand_count": hand_count,
        "hands_in_roi": hands_in_roi if hands_in_roi is not None else hand_count,
    }
    return FramePacket(
        frame_id=timestamp_ms // 33,
        timestamp_ms=timestamp_ms,
        roi=ROI(x=0, y=0, width=400, height=300),
        config_version="test-config",
        motion=MotionMetrics(mean_velocity=mean_velocity, relative_motion=relative_motion),
        landmarks=None,
        metadata=metadata,
    )


def test_session_starts_after_window_threshold() -> None:
    config = _build_config(start_window_frames=3)
    events: List[SessionEvent] = []
    manager = SessionManager(config, events.append)

    for ts in (0, 100, 200, 300):
        manager.process_frame(
            _packet(
                timestamp_ms=ts,
                mean_velocity=0.6,
                relative_motion=0.35,
                hand_count=2 if ts >= 100 else 1,
            )
        )

    assert any(e.event_type is SessionEventType.STARTED for e in events)
    start_event = next(e for e in events if e.event_type is SessionEventType.STARTED)
    assert manager.session_active is True
    assert start_event.timestamp_ms == 300


def test_session_stops_after_timeout_when_motion_drops() -> None:
    config = _build_config(stop_timeout_ms=400)
    events: List[SessionEvent] = []
    manager = SessionManager(config, events.append)

    # Start session
    for ts in (0, 100, 200):
        manager.process_frame(
            _packet(timestamp_ms=ts, mean_velocity=0.7, relative_motion=0.4)
        )

    assert manager.session_active

    inactive_timestamps = (400, 500, 650)
    for ts in inactive_timestamps:
        manager.process_frame(
            _packet(
                timestamp_ms=ts,
                mean_velocity=0.1,
                relative_motion=0.05,
                hand_count=2,
            )
        )

    end_event = next(e for e in events if e.event_type is SessionEventType.ENDED)
    assert end_event.timestamp_ms == 650
    assert manager.session_active is False


def test_relative_motion_threshold_prevents_false_start() -> None:
    config = _build_config(start_window_frames=2)
    events: List[SessionEvent] = []
    manager = SessionManager(config, events.append)

    for ts in (0, 100, 200):
        manager.process_frame(
            _packet(timestamp_ms=ts, mean_velocity=0.8, relative_motion=0.2)
        )

    assert not any(e.event_type is SessionEventType.STARTED for e in events)
    assert manager.session_active is False
