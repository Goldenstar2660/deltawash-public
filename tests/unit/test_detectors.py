from __future__ import annotations

from pathlib import Path

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
from deltawash_pi.detectors.runner import DetectorRunner, build_default_runner
from deltawash_pi.interpreter.types import FramePacket, MotionMetrics, StepID, StepOrientation


def _config() -> Config:
    steps = {
        step_id: StepThreshold(duration_ms=3000, confidence_min=0.5, orientation_hint=None)
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


def _packet(*, metadata: dict | None = None) -> FramePacket:
    return FramePacket(
        frame_id=0,
        timestamp_ms=0,
        roi=ROI(x=0, y=0, width=400, height=300),
        config_version="test-config",
        motion=MotionMetrics(mean_velocity=0.0, relative_motion=0.0),
        landmarks=None,
        metadata=metadata or {},
    )


def test_metadata_hint_sets_confident_signal() -> None:
    runner = build_default_runner(_config())
    packet = _packet(metadata={"demo_step": StepID.STEP_2.value})

    signals = runner.evaluate(packet)
    step2 = next(sig for sig in signals if sig.step_id is StepID.STEP_2)
    assert step2.is_confident is True
    assert step2.orientation is StepOrientation.NONE
    assert step2.notes is None

    others = [sig for sig in signals if sig.step_id is not StepID.STEP_2]
    assert all(sig.is_confident is False for sig in others)


def test_orientation_metadata_passthrough() -> None:
    runner = build_default_runner(_config())
    packet = _packet(
        metadata={
            "demo_step": StepID.STEP_6.value,
            "demo_orientation": StepOrientation.LEFT_THUMB.value,
        }
    )

    signal = next(sig for sig in runner.evaluate(packet) if sig.step_id is StepID.STEP_6)
    assert signal.is_confident is True
    assert signal.orientation is StepOrientation.LEFT_THUMB


def test_uncertain_when_no_metadata() -> None:
    runner = build_default_runner(_config())
    signals = runner.evaluate(_packet())
    assert all(sig.is_confident is False for sig in signals)
    assert all(sig.notes for sig in signals)


def test_runner_accepts_custom_detectors() -> None:
    class AlwaysOneDetector:
        def evaluate(self, packet: FramePacket):  # type: ignore[override]
            return type("Sig", (), {"step_id": "custom"})()

    runner = DetectorRunner([AlwaysOneDetector()])
    output = runner.evaluate(_packet())
    assert len(output) == 1
