"""ML-backed WHO step recognizer that wraps the CNN model.

This module uses the CNN-only model as the single source of truth for
hand wash step recognition. MediaPipe has been completely eliminated.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from deltawash_pi.config.loader import Config
from deltawash_pi.detectors.base import MetadataDetector
from deltawash_pi.interpreter.types import (
    FramePacket,
    StepID,
    StepOrientation,
    StepSignal,
    StepSignalSource,
)

LOGGER = logging.getLogger(__name__)

ML_LABEL_TO_STEP = {
    "Palm": StepID.STEP_2,
    "Dorsum": StepID.STEP_3,
    "Interlaced": StepID.STEP_4,
    "Interlocked": StepID.STEP_5,
    "Thumbs": StepID.STEP_6,
    "Fingertips": StepID.STEP_7,
}


@dataclass(frozen=True)
class MLStepResult:
    label: str
    confidence: float
    source: str

    @property
    def step_id(self) -> Optional[StepID]:
        return ML_LABEL_TO_STEP.get(self.label)


class MLStepRecognizer:
    """Lazy loader for the ML model package."""

    def __init__(self) -> None:
        self._analyzer = None
        self._load_error: Optional[Exception] = None
        self._warned = False
        self._infer_warned = False
        self._module = None

    def infer(self, packet: FramePacket) -> Optional[MLStepResult]:
        cached = packet.metadata.get("_ml_inference")
        if isinstance(cached, MLStepResult):
            return cached
        if isinstance(cached, dict):
            label = cached.get("label")
            confidence = cached.get("confidence")
            source = cached.get("source")
            if isinstance(label, str) and isinstance(confidence, (int, float)) and isinstance(source, str):
                return MLStepResult(label=label, confidence=float(confidence), source=source)
        if packet.image is None:
            return None
        result = self._run_inference(packet)
        if result is not None:
            packet.metadata["_ml_inference"] = {
                "label": result.label,
                "confidence": result.confidence,
                "source": result.source,
            }
        return result

    def _run_inference(self, packet: FramePacket) -> Optional[MLStepResult]:
        analyzer = self._ensure_analyzer()
        if analyzer is None:
            return None
        try:
            frame = packet.image
            if frame is None:
                return None
            frame = _apply_frame_transform(frame, packet.metadata.get("frame_transform"))
            if frame.ndim == 3 and frame.shape[2] >= 3:
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            else:
                frame_bgr = frame
            output = analyzer.process_frame(frame_bgr)
            label, confidence, source = _select_prediction(output)
            return MLStepResult(label=label, confidence=float(confidence), source=source)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            if not self._infer_warned:
                LOGGER.error("ML inference failed: %s", exc)
                self._infer_warned = True
            return None

    def _ensure_analyzer(self):
        if self._analyzer is not None:
            return self._analyzer
        if self._load_error is not None:
            if not self._warned:
                LOGGER.error("ML recognizer unavailable: %s", self._load_error)
                self._warned = True
            return None
        try:
            module = self._load_module()
            model_dir = Path(module.__file__).resolve().parent
            # CNN-only model - single file
            self._analyzer = module.DeltaWashAnalyzer(
                cnn_path=str(model_dir / "cnn_model.pth"),
            )
            return self._analyzer
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._load_error = exc
            if not self._warned:
                LOGGER.error("Failed to initialize ML recognizer: %s", exc)
                self._warned = True
            return None

    def _load_module(self):
        if self._module is not None:
            return self._module
        module = importlib.import_module("deltawash_pi.ml.model")
        self._module = module
        return module


class MLStepDetector(MetadataDetector):
    """Detector wrapper that maps ML predictions into StepSignal outputs."""

    signal_source = StepSignalSource.MODEL

    def __init__(self, config: Config, step_id: StepID, recognizer: MLStepRecognizer) -> None:
        self.step_id = step_id
        self._recognizer = recognizer
        super().__init__(config)

    def _score_packet(self, packet: FramePacket):  # type: ignore[override]
        result = self._recognizer.infer(packet)
        if result is None:
            if packet.image is None:
                return 0.0, StepOrientation.NONE, "missing_image"
            return 0.0, StepOrientation.NONE, "ml_unavailable"
        predicted_step = result.step_id
        if predicted_step is None:
            return 0.0, StepOrientation.NONE, "ml_background"
        if predicted_step is not self.step_id:
            return 0.0, StepOrientation.NONE, f"ml_predicted_{predicted_step.value.lower()}"
        orientation = _orientation_for_step(self.step_id, packet)
        return result.confidence, orientation, None

    def evaluate(self, packet: FramePacket) -> StepSignal:  # type: ignore[override]
        confidence, orientation, notes = self._compute(packet)
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


def _select_prediction(output: dict) -> tuple[str, float, str]:
    """Select prediction from CNN output.
    
    With CNN-only model, all predictions come from the same source.
    """
    # All predictions are now from CNN (pixel key for backwards compatibility)
    label, conf = output.get("pixel", ("Background", 0.0))
    return label, float(conf), "cnn"


def _apply_frame_transform(frame: np.ndarray, transform) -> np.ndarray:
    if not isinstance(transform, dict):
        return frame
    if transform.get("applied", True):
        return frame
    hflip = bool(transform.get("hflip", False))
    vflip = bool(transform.get("vflip", False))
    if hflip and vflip:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if hflip:
        return cv2.flip(frame, 1)
    if vflip:
        return cv2.flip(frame, 0)
    return frame


def _orientation_for_step(step_id: StepID, packet: FramePacket) -> StepOrientation:
    """Determine orientation for steps that require it.
    
    Without MediaPipe landmarks, we cannot determine hand orientation
    from the image alone. Return NONE for now - the CNN predicts the
    step type but not the specific orientation variant.
    """
    # Future: Could train separate CNN heads for orientation
    # For now, return NONE as orientation detection requires landmarks
    return StepOrientation.NONE


__all__ = ["MLStepDetector", "MLStepRecognizer", "MLStepResult"]
