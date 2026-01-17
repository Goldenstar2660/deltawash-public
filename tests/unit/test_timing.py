from __future__ import annotations

from pathlib import Path
from typing import List

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
from deltawash_pi.interpreter.state_machine import (
    InterpreterEvent,
    InterpreterEventType,
    InterpreterStateMachine,
)
from deltawash_pi.interpreter.types import (
    StepID,
    StepOrientation,
    StepSignal,
    StepSignalSource,
    StepState,
    StepStatus,
)


def _config(*, duration_ms: int = 300) -> Config:
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


def _signal(
    step_id: StepID,
    timestamp_ms: int,
    *,
    confidence: float = 0.9,
    orientation: StepOrientation = StepOrientation.NONE,
    is_confident: bool = True,
) -> StepSignal:
    return StepSignal(
        step_id=step_id,
        orientation=orientation,
        confidence=confidence,
        is_confident=is_confident,
        timestamp_ms=timestamp_ms,
        source=StepSignalSource.MODEL,
        notes=None,
    )


def _status(machine: InterpreterStateMachine, step_id: StepID) -> StepStatus:
    snapshot = {status.step_id: status for status in machine.snapshot()}
    return snapshot[step_id]


def test_step_completes_after_required_duration() -> None:
    config = _config(duration_ms=300)
    events: List[InterpreterEvent] = []
    machine = InterpreterStateMachine(config, events.append)
    machine.start_session("session-1", 0)

    machine.process_signals([_signal(StepID.STEP_2, 0)], 0)
    machine.process_signals([_signal(StepID.STEP_2, 150)], 150)
    machine.process_signals([_signal(StepID.STEP_2, 320)], 320)

    status = _status(machine, StepID.STEP_2)
    assert status.state is StepState.COMPLETED
    assert status.accumulated_ms >= 300

    completed_events = [
        evt
        for evt in events
        if evt.event_type is InterpreterEventType.STEP_STATE
        and evt.step_id is StepID.STEP_2
        and evt.state is StepState.COMPLETED
    ]
    assert completed_events, "completion event should be emitted"


def test_uncertainty_pauses_and_resumes_accumulation() -> None:
    config = _config(duration_ms=400)
    machine = InterpreterStateMachine(config)
    machine.start_session("session-2", 0)

    machine.process_signals([_signal(StepID.STEP_3, 0)], 0)
    machine.process_signals([_signal(StepID.STEP_3, 150)], 150)
    machine.process_signals([], 300)

    status = _status(machine, StepID.STEP_3)
    assert status.state is StepState.UNCERTAIN
    assert status.accumulated_ms == 150
    assert status.uncertainty_count == 1
    assert machine.active_step_id is None

    machine.process_signals([_signal(StepID.STEP_3, 500)], 500)
    machine.process_signals([_signal(StepID.STEP_3, 650)], 650)
    machine.process_signals([_signal(StepID.STEP_3, 820)], 820)

    status = _status(machine, StepID.STEP_3)
    assert status.state is StepState.COMPLETED
    assert status.accumulated_ms >= 400
    assert machine.active_step_id is StepID.STEP_3