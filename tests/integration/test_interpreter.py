from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

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
from deltawash_pi.interpreter.session_manager import SessionEvent, SessionEventType, SessionManager
from deltawash_pi.interpreter.state_machine import (
    InterpreterEvent,
    InterpreterEventType,
    InterpreterStateMachine,
)
from deltawash_pi.interpreter.types import (
    FramePacket,
    MotionMetrics,
    StepID,
    StepOrientation,
    StepSignal,
    StepSignalSource,
    StepState,
)


def _config(*, duration_ms: int = 250) -> Config:
    steps = {
        step_id: StepThreshold(duration_ms=duration_ms, confidence_min=0.5, orientation_hint=None)
        for step_id in VALID_STEP_IDS
    }
    return Config(
        source=Path("config.yaml"),
        config_version="test-config",
        roi=ROI(x=0, y=0, width=400, height=300),
        session=SessionConfig(
            motion_threshold=0.4,
            relative_motion_threshold=0.3,
            start_window_frames=3,
            stop_timeout_ms=500,
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
    hand_count: int,
) -> FramePacket:
    metadata = {
        "hand_count": hand_count,
        "hands_in_roi": hand_count,
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


def _signal(step_id: StepID, timestamp_ms: int, *, orientation: StepOrientation = StepOrientation.NONE) -> StepSignal:
    return StepSignal(
        step_id=step_id,
        orientation=orientation,
        confidence=0.9,
        is_confident=True,
        timestamp_ms=timestamp_ms,
        source=StepSignalSource.MODEL,
        notes=None,
    )


def _emit(
    manager: SessionManager,
    machine: InterpreterStateMachine,
    *,
    timestamp_ms: int,
    signals: Sequence[StepSignal],
    mean_velocity: float = 0.8,
    relative_motion: float = 0.5,
    hand_count: int = 2,
) -> None:
    manager.process_frame(
        _packet(
            timestamp_ms=timestamp_ms,
            mean_velocity=mean_velocity,
            relative_motion=relative_motion,
            hand_count=hand_count,
        )
    )
    machine.process_signals(signals, timestamp_ms)


def test_steps_complete_out_of_order_through_session_pipeline() -> None:
    config = _config(duration_ms=250)
    interpreter_events: List[InterpreterEvent] = []

    machine = InterpreterStateMachine(config, interpreter_events.append)
    session_events: List[SessionEvent] = []

    def _handle_session(event: SessionEvent) -> None:
        session_events.append(event)
        if event.event_type is SessionEventType.STARTED:
            machine.start_session(event.session_id, event.timestamp_ms)
        elif event.event_type is SessionEventType.ENDED:
            machine.end_session(event.timestamp_ms)

    manager = SessionManager(config, _handle_session)

    for ts in (0, 100, 200, 300):
        manager.process_frame(_packet(timestamp_ms=ts, mean_velocity=0.8, relative_motion=0.5, hand_count=2))

    assert manager.session_active
    assert manager.current_session_id is not None

    for ts in (400, 500, 600, 700):
        _emit(manager, machine, timestamp_ms=ts, signals=[_signal(StepID.STEP_4, ts)])

    for ts in (800, 900):
        _emit(manager, machine, timestamp_ms=ts, signals=[])

    for ts in (1000, 1100, 1200, 1300):
        _emit(
            manager,
            machine,
            timestamp_ms=ts,
            signals=[_signal(StepID.STEP_2, ts, orientation=StepOrientation.RIGHT_OVER_LEFT)],
        )

    for ts in (1500, 1700, 1900, 2100):
        manager.process_frame(
            _packet(timestamp_ms=ts, mean_velocity=0.05, relative_motion=0.02, hand_count=0)
        )

    assert manager.session_active is False
    assert any(evt.event_type is SessionEventType.STARTED for evt in session_events)
    assert any(evt.event_type is SessionEventType.ENDED for evt in session_events)

    status_map = {status.step_id: status for status in machine.snapshot()}
    step4 = status_map[StepID.STEP_4]
    step2 = status_map[StepID.STEP_2]

    assert step4.state is StepState.COMPLETED
    assert step2.state is StepState.COMPLETED
    assert step4.completed_ts is not None and step2.completed_ts is not None
    assert step4.completed_ts < step2.completed_ts

    completed_pairs = [
        (event.step_id, event.state)
        for event in interpreter_events
        if event.event_type is InterpreterEventType.STEP_STATE and event.state is StepState.COMPLETED
    ]
    assert (StepID.STEP_4, StepState.COMPLETED) in completed_pairs
    assert (StepID.STEP_2, StepState.COMPLETED) in completed_pairs

    assert machine.active_step_id is None
