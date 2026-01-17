"""Detector base classes for WHO Steps 2-7."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Tuple

from deltawash_pi.config.loader import Config, StepThreshold
from deltawash_pi.interpreter.types import (
    FramePacket,
    StepID,
    StepOrientation,
    StepSignal,
    StepSignalSource,
)


class BaseDetector(ABC):
    """Shared detector wiring that enforces confidence gating."""

    step_id: StepID
    signal_source: StepSignalSource = StepSignalSource.HEURISTIC

    def __init__(self, config: Config):
        self._config = config
        try:
            self._step_config: StepThreshold = config.steps[self.step_id.value]
        except KeyError as exc:  # pragma: no cover - config schema guarantees keys
            raise ValueError(f"Missing step config for {self.step_id.value}") from exc

    def evaluate(self, packet: FramePacket) -> StepSignal:
        confidence, orientation, notes = self._compute(packet)
        scale = packet.metadata.get("_hand_pair_confidence_scale")
        if isinstance(scale, (int, float)):
            confidence *= float(scale)
        is_confident = confidence >= self._step_config.confidence_min
        if not is_confident and notes is None:
            notes = "insufficient_confidence"
        return StepSignal(
            step_id=self.step_id,
            orientation=orientation,
            confidence=confidence,
            is_confident=is_confident,
            timestamp_ms=packet.timestamp_ms,
            source=self.signal_source,
            notes=notes,
        )

    @abstractmethod
    def _compute(self, packet: FramePacket) -> Tuple[float, StepOrientation, Optional[str]]:
        """Return (confidence, orientation, notes)."""


class MetadataDetector(BaseDetector):
    """Detector that trusts demo metadata hints until real models arrive."""

    def _compute(self, packet: FramePacket) -> Tuple[float, StepOrientation, Optional[str]]:
        if packet.metadata.get("_disable_demo_hints"):
            return self._score_packet(packet)
        hint = packet.metadata.get("demo_step")
        if isinstance(hint, str) and hint == self.step_id.value:
            return 1.0, self._orientation_from_metadata(packet), None
        return self._score_packet(packet)

    def _score_packet(self, packet: FramePacket) -> Tuple[float, StepOrientation, Optional[str]]:
        # Placeholder heuristics until MediaPipe-based cues land in later phases.
        return 0.0, StepOrientation.NONE, "no_demo_hint"

    def _orientation_from_metadata(self, packet: FramePacket) -> StepOrientation:
        orientation = packet.metadata.get("demo_orientation")
        if isinstance(orientation, str):
            try:
                return StepOrientation(orientation)
            except ValueError:
                return StepOrientation.NONE
        return StepOrientation.NONE


__all__ = ["BaseDetector", "MetadataDetector"]
