"""Deterministic demo asset manifest loader and replay scaffolding."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from deltawash_pi.config.loader import Config, ROI
from deltawash_pi.interpreter.types import FramePacket, MotionMetrics, StepID, StepOrientation


class ManifestError(ValueError):
    """Raised when the demo manifest fails validation."""


@dataclass(frozen=True)
class StepAnnotation:
    step_id: StepID
    orientation: StepOrientation
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class DemoAsset:
    asset_id: str
    path: Path
    fps: float
    total_frames: int
    annotations: List[StepAnnotation]
    roi: Optional[ROI]


@dataclass(frozen=True)
class DemoManifest:
    version: str
    assets: Dict[str, DemoAsset]

    def require(self, asset_id: str) -> DemoAsset:
        try:
            return self.assets[asset_id]
        except KeyError as exc:  # pragma: no cover - defensive
            raise ManifestError(f"Unknown asset id: {asset_id}") from exc


def load_manifest(path: str | Path) -> DemoManifest:
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise ManifestError(f"Manifest not found: {manifest_path}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ManifestError("Manifest root must be a JSON object")

    version = data.get("version")
    if not isinstance(version, str):
        raise ManifestError("Manifest must include a string 'version'")

    assets_block = data.get("assets")
    if not isinstance(assets_block, list):
        raise ManifestError("Manifest 'assets' must be an array")

    assets: Dict[str, DemoAsset] = {}
    for entry in assets_block:
        if not isinstance(entry, dict):
            raise ManifestError("Each asset entry must be an object")
        asset_id = _require_str(entry, "id")
        if asset_id in assets:
            raise ManifestError(f"Duplicate asset id: {asset_id}")

        raw_file = _require_str(entry, "file")
        path = (manifest_path.parent / raw_file).resolve()
        fps = _require_positive_float(entry, "fps")
        total_frames = _require_positive_int(entry, "total_frames")

        roi = None
        if "roi" in entry:
            roi_block = entry["roi"]
            if not isinstance(roi_block, dict):
                raise ManifestError("roi block must be an object when provided")
            roi = ROI(
                x=_require_positive_int(roi_block, "x", allow_zero=True),
                y=_require_positive_int(roi_block, "y", allow_zero=True),
                width=_require_positive_int(roi_block, "width"),
                height=_require_positive_int(roi_block, "height"),
            )

        annotations_block = entry.get("annotations", [])
        annotations: List[StepAnnotation] = []
        for annotation in annotations_block:
            if not isinstance(annotation, dict):
                raise ManifestError("annotations entries must be objects")
            step_id = StepID(_require_str(annotation, "step_id"))
            orientation_value = annotation.get("orientation", StepOrientation.NONE.value)
            orientation = StepOrientation(orientation_value)
            start_ms = _require_positive_int(annotation, "start_ms", allow_zero=True)
            end_ms = _require_positive_int(annotation, "end_ms")
            if end_ms <= start_ms:
                raise ManifestError(
                    f"Annotation end_ms must be greater than start_ms (step {step_id} in asset {asset_id})"
                )
            annotations.append(
                StepAnnotation(
                    step_id=step_id,
                    orientation=orientation,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
            )

        assets[asset_id] = DemoAsset(
            asset_id=asset_id,
            path=path,
            fps=fps,
            total_frames=total_frames,
            annotations=annotations,
            roi=roi,
        )

    return DemoManifest(version=version, assets=assets)


class DemoReplay:
    """Streams placeholder FramePacket objects for deterministic testing."""

    def __init__(self, manifest: DemoManifest, config: Config):
        self._manifest = manifest
        self._config = config

    def stream_packets(self, asset_id: str) -> Iterator[FramePacket]:
        asset = self._manifest.require(asset_id)
        roi = asset.roi or self._config.roi
        frame_interval_ms = max(1, int(round(1000.0 / asset.fps)))
        base_metadata = {"asset_id": asset.asset_id, "demo_mode": True}

        for frame_id in range(asset.total_frames):
            timestamp_ms = frame_id * frame_interval_ms
            metadata = dict(base_metadata)
            metadata["timestamp_offset_ms"] = timestamp_ms
            metadata["demo_frame_interval_ms"] = frame_interval_ms
            annotation = _annotation_for_timestamp(asset.annotations, timestamp_ms)
            if annotation:
                metadata["demo_step"] = annotation.step_id.value
                metadata["demo_orientation"] = annotation.orientation.value
                metadata["demo_step_start_ms"] = annotation.start_ms
                metadata["demo_step_end_ms"] = annotation.end_ms
            yield FramePacket(
                frame_id=frame_id,
                timestamp_ms=timestamp_ms,
                roi=roi,
                config_version=self._config.config_version,
                motion=MotionMetrics(mean_velocity=0.0, relative_motion=0.0),
                landmarks=None,
                metadata=metadata,
            )


def summarize_step_durations(asset: DemoAsset) -> Dict[StepID, int]:
    """Sum annotated durations per step for a demo asset."""

    totals: Dict[StepID, int] = {}
    frame_interval_ms = max(1, int(round(1000.0 / asset.fps)))
    asset_end_ms = asset.total_frames * frame_interval_ms
    for annotation in asset.annotations:
        start_ms = annotation.start_ms
        end_ms = min(annotation.end_ms, asset_end_ms)
        if end_ms <= start_ms:
            continue
        duration = end_ms - start_ms
        if duration <= 0:
            continue
        totals[annotation.step_id] = totals.get(annotation.step_id, 0) + duration
    return totals


def _require_str(obj: Dict[str, object], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"'{key}' must be a non-empty string")
    return value


def _require_positive_int(obj: Dict[str, object], key: str, *, allow_zero: bool = False) -> int:
    value = obj.get(key)
    if not isinstance(value, int):
        raise ManifestError(f"'{key}' must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise ManifestError(f"'{key}' must be >= {minimum}")
    return value


def _require_positive_float(obj: Dict[str, object], key: str) -> float:
    value = obj.get(key)
    if not isinstance(value, (int, float)):
        raise ManifestError(f"'{key}' must be a number")
    result = float(value)
    if result <= 0:
        raise ManifestError(f"'{key}' must be greater than 0")
    return result


def _annotation_for_timestamp(annotations: List[StepAnnotation], timestamp_ms: int) -> Optional[StepAnnotation]:
    for annotation in annotations:
        if annotation.start_ms <= timestamp_ms < annotation.end_ms:
            return annotation
    return None


__all__ = [
    "DemoAsset",
    "DemoManifest",
    "DemoReplay",
    "ManifestError",
    "StepAnnotation",
    "load_manifest",
    "summarize_step_durations",
]
