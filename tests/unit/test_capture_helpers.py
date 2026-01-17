from __future__ import annotations

import numpy as np

from deltawash_pi.cli._demo_utils import DemoSignalSynthesizer, boost_demo_packet
from deltawash_pi.cli.capture import MotionEstimator
from deltawash_pi.config.loader import ROI, load_config
from deltawash_pi.interpreter.types import FramePacket, MotionMetrics, StepID, StepOrientation

from tests.unit.test_config_loader import _base_config_dict, _write_config


def _make_config(tmp_path):
    data = _base_config_dict()
    path = _write_config(tmp_path, data)
    return load_config(path)


def test_demo_packet_defaults_apply_metadata(tmp_path) -> None:
    config = _make_config(tmp_path)
    packet = FramePacket(
        frame_id=0,
        timestamp_ms=0,
        roi=config.roi,
        config_version=config.config_version,
        motion=MotionMetrics(mean_velocity=0.0, relative_motion=0.0),
        landmarks=None,
        metadata={},
    )

    enriched = boost_demo_packet(packet, config)

    assert enriched.metadata["hand_count"] == 2
    assert enriched.metadata["hands_in_roi"] == 2
    assert enriched.motion.mean_velocity >= config.session.motion_threshold
    assert enriched.motion.relative_motion >= config.session.relative_motion_threshold


def test_demo_signal_synthesizer_yields_confident_signal(tmp_path) -> None:
    config = _make_config(tmp_path)
    synthesizer = DemoSignalSynthesizer()
    packet_one = FramePacket(
        frame_id=0,
        timestamp_ms=1234,
        roi=config.roi,
        config_version=config.config_version,
        motion=MotionMetrics(mean_velocity=1.0, relative_motion=1.0),
        landmarks=None,
        metadata={
            "demo_step": StepID.STEP_3.value,
            "demo_orientation": StepOrientation.RIGHT_OVER_LEFT.value,
            "demo_step_start_ms": 1200,
            "demo_frame_interval_ms": 40,
            "demo_step_end_ms": 2000,
        },
    )
    packet_two = FramePacket(
        frame_id=1,
        timestamp_ms=1274,
        roi=config.roi,
        config_version=config.config_version,
        motion=MotionMetrics(mean_velocity=1.0, relative_motion=1.0),
        landmarks=None,
        metadata=dict(packet_one.metadata),
    )

    first = synthesizer.generate(packet_one)[0]
    second = synthesizer.generate(packet_two)[0]
    tail = synthesizer.flush()

    assert first.step_id is StepID.STEP_3
    assert first.orientation is StepOrientation.RIGHT_OVER_LEFT
    assert first.timestamp_ms == 1200
    assert second.timestamp_ms == 1240
    assert not tail  # no flush needed mid-annotation


def test_demo_signal_synthesizer_ignores_invalid_metadata(tmp_path) -> None:
    config = _make_config(tmp_path)
    synthesizer = DemoSignalSynthesizer()
    packet = FramePacket(
        frame_id=0,
        timestamp_ms=0,
        roi=config.roi,
        config_version=config.config_version,
        motion=MotionMetrics(mean_velocity=1.0, relative_motion=1.0),
        landmarks=None,
        metadata={"demo_step": "UNKNOWN"},
    )

    assert synthesizer.generate(packet) == []


def test_demo_signal_timestamp_clamps_to_annotation_end(tmp_path) -> None:
    config = _make_config(tmp_path)
    synthesizer = DemoSignalSynthesizer()
    packet_one = FramePacket(
        frame_id=0,
        timestamp_ms=1500,
        roi=config.roi,
        config_version=config.config_version,
        motion=MotionMetrics(mean_velocity=1.0, relative_motion=1.0),
        landmarks=None,
        metadata={
            "demo_step": StepID.STEP_2.value,
            "demo_step_start_ms": 1000,
            "demo_frame_interval_ms": 40,
            "demo_step_end_ms": 2000,
        },
    )
    packet_two = FramePacket(
        frame_id=1,
        timestamp_ms=1980,
        roi=config.roi,
        config_version=config.config_version,
        motion=MotionMetrics(mean_velocity=1.0, relative_motion=1.0),
        landmarks=None,
        metadata=dict(packet_one.metadata),
    )

    synthesizer.generate(packet_one)
    final_signal = synthesizer.generate(packet_two)[0]

    assert final_signal.timestamp_ms == 2000
    assert synthesizer.flush() == []


def test_motion_estimator_detects_change() -> None:
    estimator = MotionEstimator()
    roi = ROI(x=0, y=0, width=2, height=2)
    frame_one = np.zeros((4, 4, 3), dtype=np.uint8)
    no_motion = estimator.compute(frame_one, roi)
    assert no_motion.mean_velocity == 0.0
    assert no_motion.relative_motion == 0.0

    frame_two = np.full((4, 4, 3), 255, dtype=np.uint8)
    motion = estimator.compute(frame_two, roi)
    assert motion.mean_velocity > 0
    assert motion.relative_motion > 0
