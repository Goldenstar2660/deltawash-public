"""Detector runner that evaluates all WHO step detectors per frame."""

from __future__ import annotations

from typing import Iterable, List, Optional

from deltawash_pi.config.loader import Config
from deltawash_pi.detectors._geometry import HandPair, select_hand_pair
from deltawash_pi.detectors.base import BaseDetector
from deltawash_pi.detectors.ml import MLStepDetector, MLStepRecognizer
from deltawash_pi.interpreter.types import FramePacket, StepID, StepSignal


class DetectorRunner:
    """Evaluates every detector for each FramePacket."""

    def __init__(self, detectors: Iterable[BaseDetector], *, pair_cache_ms: int = 5000):
        self._detectors = list(detectors)
        self._pair_cache_ms = max(0, pair_cache_ms)
        self._cached_pair: Optional[HandPair] = None
        self._cached_ts: Optional[int] = None

    def evaluate(self, packet: FramePacket) -> List[StepSignal]:
        self._prime_pair_cache(packet)
        return [detector.evaluate(packet) for detector in self._detectors]

    def _prime_pair_cache(self, packet: FramePacket) -> None:
        if self._pair_cache_ms <= 0:
            return
        pair, _ = select_hand_pair(packet)
        if pair is not None:
            self._cached_pair = pair
            self._cached_ts = packet.timestamp_ms
            packet.metadata["_hand_pair_cache"] = pair
            packet.metadata["_hand_pair_confidence_scale"] = 1.0
            return
        if self._cached_pair is None or self._cached_ts is None:
            return
        age = packet.timestamp_ms - self._cached_ts
        if age < 0 or age > self._pair_cache_ms:
            return
        packet.metadata["_hand_pair_cache"] = self._cached_pair
        packet.metadata["_hand_pair_confidence_scale"] = max(0.7, 1.0 - (age / self._pair_cache_ms) * 0.3)


def build_default_runner(config: Config) -> DetectorRunner:
    recognizer = MLStepRecognizer()
    detectors: List[BaseDetector] = [
        MLStepDetector(config, StepID.STEP_2, recognizer),
        MLStepDetector(config, StepID.STEP_3, recognizer),
        MLStepDetector(config, StepID.STEP_4, recognizer),
        MLStepDetector(config, StepID.STEP_5, recognizer),
        MLStepDetector(config, StepID.STEP_6, recognizer),
        MLStepDetector(config, StepID.STEP_7, recognizer),
    ]
    return DetectorRunner(detectors)


__all__ = ["DetectorRunner", "build_default_runner"]
