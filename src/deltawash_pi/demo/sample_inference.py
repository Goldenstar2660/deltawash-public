"""Deterministic sample ML inference generator for end-to-end testing."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Optional

from deltawash_pi.interpreter.types import FramePacket, StepID

STEP_TO_LABEL: Dict[StepID, str] = {
    StepID.STEP_2: "Palm",
    StepID.STEP_3: "Dorsum",
    StepID.STEP_4: "Interlaced",
    StepID.STEP_5: "Interlocked",
    StepID.STEP_6: "Thumbs",
    StepID.STEP_7: "Fingertips",
}

LABELS = list(STEP_TO_LABEL.values())


@dataclass(frozen=True)
class SampleInferenceConfig:
    base_confidence: float = 0.78
    peak_boost: float = 0.12
    jitter: float = 0.08
    dropout_rate: float = 0.08
    mislabel_rate: float = 0.04


class SampleInferenceSynthesizer:
    """Builds a deterministic ML-like prediction for each demo frame."""

    def __init__(self, config: Optional[SampleInferenceConfig] = None) -> None:
        self._config = config or SampleInferenceConfig()

    def infer(self, packet: FramePacket) -> Dict[str, object]:
        asset_id = packet.metadata.get("asset_id", "sample")
        seed = f"{asset_id}:{packet.frame_id}:{packet.timestamp_ms}"
        rand_drop = _stable_unit(f"{seed}:dropout")
        rand_mislabel = _stable_unit(f"{seed}:mislabel")
        rand_jitter = _stable_unit(f"{seed}:jitter")

        step_id = _step_id_from_metadata(packet)
        label = STEP_TO_LABEL.get(step_id) if step_id else None
        confidence = _confidence_for_packet(packet, rand_jitter, self._config)

        if rand_drop < self._config.dropout_rate:
            return _result("Background", min(0.25, confidence))
        if label and rand_mislabel < self._config.mislabel_rate:
            label = _mislabel(label, rand_mislabel)
            return _result(label, max(0.35, confidence * 0.6))
        if label:
            return _result(label, confidence)
        return _result("Background", min(0.2, confidence))


def _step_id_from_metadata(packet: FramePacket) -> Optional[StepID]:
    step_value = packet.metadata.get("demo_step")
    if not isinstance(step_value, str):
        return None
    try:
        return StepID(step_value)
    except ValueError:
        return None


def _confidence_for_packet(
    packet: FramePacket, jitter: float, config: SampleInferenceConfig
) -> float:
    start_ms = _coerce_int(packet.metadata.get("demo_step_start_ms"))
    end_ms = _coerce_int(packet.metadata.get("demo_step_end_ms"))
    timestamp = packet.timestamp_ms
    if start_ms is None or end_ms is None or end_ms <= start_ms:
        base = config.base_confidence
        return _clamp(base + (jitter - 0.5) * config.jitter)
    progress = (timestamp - start_ms) / (end_ms - start_ms)
    progress = _clamp(progress, low=0.0, high=1.0)
    shape = 1.0 - abs(progress - 0.5) * 2.0
    base = config.base_confidence + config.peak_boost * shape
    return _clamp(base + (jitter - 0.5) * config.jitter, low=0.05, high=0.98)


def _mislabel(label: str, rand_value: float) -> str:
    options = [candidate for candidate in LABELS if candidate != label]
    if not options:
        return "Background"
    index = int(rand_value * len(options)) % len(options)
    return options[index]


def _result(label: str, confidence: float) -> Dict[str, object]:
    return {"label": label, "confidence": float(confidence), "source": "sample"}


def _stable_unit(seed: str) -> float:
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _clamp(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _coerce_int(value: object) -> Optional[int]:
    if isinstance(value, int):
        return value
    return None


__all__ = ["SampleInferenceConfig", "SampleInferenceSynthesizer"]
