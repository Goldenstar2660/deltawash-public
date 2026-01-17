"""Shared helpers for deterministic demo pipelines."""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Tuple

from deltawash_pi.config.loader import Config
from deltawash_pi.interpreter.types import (
    FramePacket,
    MotionMetrics,
    StepID,
    StepOrientation,
    StepSignal,
    StepSignalSource,
)


def boost_demo_packet(packet: FramePacket, config: Config) -> FramePacket:
    """Ensure demo packets satisfy session gating thresholds."""

    metadata = dict(packet.metadata)
    metadata.setdefault("hand_count", 2)
    metadata.setdefault("hands_in_roi", 2)
    threshold_motion = max(0.5, config.session.motion_threshold * 1.1)
    threshold_relative = max(0.3, config.session.relative_motion_threshold * 1.1)
    boosted_motion = MotionMetrics(
        mean_velocity=max(packet.motion.mean_velocity, threshold_motion),
        relative_motion=max(packet.motion.relative_motion, threshold_relative),
    )
    return replace(packet, motion=boosted_motion, metadata=metadata)


def override_step_durations(config: Config, durations: Dict[StepID, int]) -> Config:
    """Return a config copy with step durations overridden for demo playback."""

    if not durations:
        return config
    new_steps = {}
    for step_id, threshold in config.steps.items():
        step_key = StepID(step_id)
        duration = durations.get(step_key)
        if isinstance(duration, int) and duration > 0:
            new_steps[step_id] = replace(threshold, duration_ms=duration)
        else:
            new_steps[step_id] = threshold
    return replace(config, steps=new_steps)


SegmentKey = Tuple[StepID, int, int, StepOrientation]


class DemoSignalSynthesizer:
    """Generates confident StepSignals from demo annotations with timing state."""

    def __init__(self) -> None:
        self._elapsed_ms: Dict[SegmentKey, int] = {}

    def generate(self, packet: FramePacket) -> List[StepSignal]:
        step_value = packet.metadata.get("demo_step")
        if not isinstance(step_value, str):
            return []
        try:
            step_id = StepID(step_value)
        except ValueError:
            return []
        orientation = _parse_orientation(packet.metadata.get("demo_orientation"))
        start_ms = _coerce_int(packet.metadata.get("demo_step_start_ms"), fallback=packet.timestamp_ms)
        end_ms = _coerce_int(packet.metadata.get("demo_step_end_ms"), fallback=start_ms)
        if end_ms < start_ms:
            end_ms = start_ms
        duration = max(0, end_ms - start_ms)
        frame_interval = _coerce_positive_int(packet.metadata.get("demo_frame_interval_ms"), default=1)
        segment_key: SegmentKey = (step_id, start_ms, end_ms, orientation)
        elapsed = self._elapsed_ms.get(segment_key, 0)
        if duration == 0:
            increment = frame_interval
            timestamp_ms = start_ms if elapsed == 0 else start_ms + elapsed
            elapsed += increment
        else:
            remaining = max(0, duration - elapsed)
            if remaining == 0:
                return []
            is_last_frame = packet.timestamp_ms + frame_interval >= end_ms
            if is_last_frame:
                timestamp_ms = start_ms + duration
                elapsed = duration
            else:
                increment = min(frame_interval, remaining)
                timestamp_ms = start_ms if elapsed == 0 else start_ms + elapsed
                elapsed += increment
        self._elapsed_ms[segment_key] = elapsed
        signal = StepSignal(
            step_id=step_id,
            orientation=orientation,
            confidence=1.0,
            is_confident=True,
            timestamp_ms=timestamp_ms,
            source=StepSignalSource.DEMO,
            notes="demo_annotation",
        )
        return [signal]

    def flush(self, *, force: bool = False) -> List[StepSignal]:
        """Emit padding signals so every annotated segment reaches completion."""

        if not force:
            return []
        pending: List[StepSignal] = []
        for segment_key in list(self._elapsed_ms.keys()):
            elapsed = self._elapsed_ms.get(segment_key, 0)
            step_id, start_ms, end_ms, orientation = segment_key
            duration = max(0, end_ms - start_ms)
            if duration <= 0 or elapsed <= 0 or elapsed >= duration:
                continue
            timestamp_ms = start_ms if duration == 0 else start_ms + duration
            pending.append(
                StepSignal(
                    step_id=step_id,
                    orientation=orientation,
                    confidence=1.0,
                    is_confident=True,
                    timestamp_ms=timestamp_ms,
                    source=StepSignalSource.DEMO,
                    notes="demo_annotation",
                )
            )
            self._elapsed_ms[segment_key] = duration
        return pending


def _parse_orientation(value: object) -> StepOrientation:
    if isinstance(value, str):
        try:
            return StepOrientation(value)
        except ValueError:
            return StepOrientation.NONE
    return StepOrientation.NONE


def _coerce_int(value: object, *, fallback: int) -> int:
    if isinstance(value, int):
        return value
    return fallback


def _coerce_positive_int(value: object, *, default: int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    return default


__all__ = ["boost_demo_packet", "DemoSignalSynthesizer", "override_step_durations"]
