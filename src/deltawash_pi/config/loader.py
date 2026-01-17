"""Config loader with schema validation for WHO steps 2-7 compliance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

VALID_STEP_IDS = ("STEP_2", "STEP_3", "STEP_4", "STEP_5", "STEP_6", "STEP_7")


class ConfigError(ValueError):
    """Raised when a configuration file fails validation."""


@dataclass(frozen=True)
class Resolution:
    width: int
    height: int


@dataclass(frozen=True)
class ROI:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class SessionConfig:
    motion_threshold: float
    relative_motion_threshold: float
    start_window_frames: int
    stop_timeout_ms: int
    min_hands: int
    require_motion: bool


@dataclass(frozen=True)
class StepThreshold:
    duration_ms: int
    confidence_min: float
    orientation_hint: Optional[str]


@dataclass(frozen=True)
class Esp8266Config:
    enabled: bool
    host: Optional[str] = None
    endpoint: Optional[str] = None
    timeout_ms: int = 500
    blink_hz: float = 1.0


@dataclass(frozen=True)
class VideoCaptureConfig:
    enabled: bool
    storage_path: Optional[Path]
    retention_seconds: Optional[int]
    max_sessions: Optional[int]


@dataclass(frozen=True)
class DemoRecordingConfig:
    enabled: bool
    output_path: Optional[Path]


@dataclass(frozen=True)
class HandTrackingConfig:
    max_num_hands: int
    model_complexity: int
    min_detection_confidence: float
    min_tracking_confidence: float
    smoothing_window: int


@dataclass(frozen=True)
class Config:
    source: Path
    config_version: str
    roi: ROI
    session: SessionConfig
    steps: Dict[str, StepThreshold]
    esp8266: Esp8266Config
    video_capture: VideoCaptureConfig
    demo_recording: DemoRecordingConfig
    resolution: Optional[Resolution]
    hand_tracking: HandTrackingConfig


def load_config(path: str | Path) -> Config:
    """Load and validate a YAML/JSON config file."""
    source = Path(path)
    if not source.exists():
        raise ConfigError(f"Config file not found: {source}")

    data = _deserialize(source)
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping")
    return _parse_config(data, source)


def _deserialize(source: Path) -> Any:
    text = source.read_text(encoding="utf-8")
    suffix = source.suffix.lower()
    if suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _parse_config(data: Dict[str, Any], source: Path) -> Config:
    config_version = _require_str(data, "config_version")
    roi_section = _require_dict(data, "roi")
    roi = ROI(
        x=_require_int(roi_section, "x", minimum=0),
        y=_require_int(roi_section, "y", minimum=0),
        width=_require_int(roi_section, "width", minimum=1),
        height=_require_int(roi_section, "height", minimum=1),
    )

    session_section = _require_dict(data, "session")
    session = SessionConfig(
        motion_threshold=_require_float(session_section, "motion_threshold", minimum=0.0),
        relative_motion_threshold=_require_float(session_section, "relative_motion_threshold", minimum=0.0),
        start_window_frames=_require_int(session_section, "start_window_frames", minimum=1),
        stop_timeout_ms=_require_int(session_section, "stop_timeout_ms", minimum=1),
        min_hands=_coerce_int(session_section.get("min_hands", 2), "session.min_hands", minimum=1),
        require_motion=bool(session_section.get("require_motion", True)),
    )

    steps_section = _require_dict(data, "steps")
    steps: Dict[str, StepThreshold] = {}
    for step_id in VALID_STEP_IDS:
        entry = _require_dict(steps_section, step_id)
        steps[step_id] = StepThreshold(
            duration_ms=_require_int(entry, "duration_ms", minimum=1),
            confidence_min=_require_float(entry, "confidence_min", minimum=0.0, maximum=1.0),
            orientation_hint=entry.get("orientation_hint"),
        )

    esp8266_section = data.get("esp8266", {})
    if not isinstance(esp8266_section, dict):
        raise ConfigError("esp8266 block must be a mapping if provided")
    esp8266 = Esp8266Config(
        enabled=bool(esp8266_section.get("enabled", False)),
        host=esp8266_section.get("host"),
        endpoint=esp8266_section.get("endpoint"),
        timeout_ms=_coerce_int(esp8266_section.get("timeout_ms", 500), "esp8266.timeout_ms", minimum=1),
        blink_hz=float(esp8266_section.get("blink_hz", 1.0)),
    )
    if esp8266.enabled and not (esp8266.host or esp8266.endpoint):
        raise ConfigError("esp8266.host (preferred) or esp8266.endpoint is required when esp8266.enabled is true")

    video_section = data.get("video_capture", {})
    if not isinstance(video_section, dict):
        raise ConfigError("video_capture block must be a mapping if provided")
    video_capture = VideoCaptureConfig(
        enabled=bool(video_section.get("enabled", False)),
        storage_path=_optional_path(video_section.get("storage_path")),
        retention_seconds=_optional_int(video_section.get("retention_seconds"), "video_capture.retention_seconds", minimum=0),
        max_sessions=_optional_int(video_section.get("max_sessions"), "video_capture.max_sessions", minimum=0),
    )
    if video_capture.enabled:
        if video_capture.storage_path is None:
            raise ConfigError("video_capture.storage_path is required when video_capture.enabled is true")
        if not video_capture.storage_path.is_absolute():
            raise ConfigError("video_capture.storage_path must be absolute")
        if video_capture.retention_seconds and video_capture.max_sessions:
            raise ConfigError("video_capture.retention_seconds and max_sessions cannot both be non-zero")

    demo_section = data.get("demo_recording", {})
    if not isinstance(demo_section, dict):
        raise ConfigError("demo_recording block must be a mapping if provided")
    demo_recording = DemoRecordingConfig(
        enabled=bool(demo_section.get("enabled", False)),
        output_path=_optional_path(demo_section.get("output_path")),
    )
    if demo_recording.enabled:
        if demo_recording.output_path is None:
            raise ConfigError("demo_recording.output_path is required when demo_recording.enabled is true")
        if not demo_recording.output_path.is_absolute():
            raise ConfigError("demo_recording.output_path must be absolute")

    resolution = None
    if "resolution" in data:
        res_section = _require_dict(data, "resolution")
        resolution = Resolution(
            width=_require_int(res_section, "width", minimum=1),
            height=_require_int(res_section, "height", minimum=1),
        )
        _validate_roi_within_resolution(roi, resolution)

    hand_section = data.get("hand_tracking", {})
    if not isinstance(hand_section, dict):
        raise ConfigError("hand_tracking block must be a mapping if provided")
    hand_tracking = HandTrackingConfig(
        max_num_hands=_coerce_int(hand_section.get("max_num_hands", 2), "hand_tracking.max_num_hands", minimum=1),
        model_complexity=_coerce_int(hand_section.get("model_complexity", 1), "hand_tracking.model_complexity", minimum=0),
        min_detection_confidence=_require_float(
            {"min_detection_confidence": hand_section.get("min_detection_confidence", 0.3)},
            "min_detection_confidence",
            minimum=0.0,
            maximum=1.0,
        ),
        min_tracking_confidence=_require_float(
            {"min_tracking_confidence": hand_section.get("min_tracking_confidence", 0.3)},
            "min_tracking_confidence",
            minimum=0.0,
            maximum=1.0,
        ),
        smoothing_window=_coerce_int(hand_section.get("smoothing_window", 4), "hand_tracking.smoothing_window", minimum=1),
    )
    if hand_tracking.model_complexity not in (0, 1, 2):
        raise ConfigError("hand_tracking.model_complexity must be 0, 1, or 2")

    return Config(
        source=source,
        config_version=config_version,
        roi=roi,
        session=session,
        steps=steps,
        esp8266=esp8266,
        video_capture=video_capture,
        demo_recording=demo_recording,
        resolution=resolution,
        hand_tracking=hand_tracking,
    )


def _validate_roi_within_resolution(roi: ROI, resolution: Resolution) -> None:
    if roi.x + roi.width > resolution.width or roi.y + roi.height > resolution.height:
        raise ConfigError("ROI rectangle exceeds configured resolution bounds")


def _require_dict(obj: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = obj.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"'{key}' must be a mapping")
    return value


def _require_str(obj: Dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"'{key}' must be a non-empty string")
    return value


def _require_int(obj: Dict[str, Any], key: str, minimum: Optional[int] = None) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"'{key}' must be an integer")
    if minimum is not None and value < minimum:
        raise ConfigError(f"'{key}' must be >= {minimum}")
    return value


def _coerce_int(value: Any, field: str, minimum: Optional[int] = None) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"'{field}' must be an integer, not boolean")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"'{field}' must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise ConfigError(f"'{field}' must be >= {minimum}")
    return parsed


def _optional_int(value: Any, field: str, minimum: Optional[int] = None) -> Optional[int]:
    if value in (None, "", False):
        return None
    return _coerce_int(value, field, minimum=minimum)


def _require_float(
    obj: Dict[str, Any],
    key: str,
    *,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> float:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"'{key}' must be a number")
    result = float(value)
    if minimum is not None and result <= minimum:
        raise ConfigError(f"'{key}' must be greater than {minimum}")
    if maximum is not None and result > maximum:
        raise ConfigError(f"'{key}' must be <= {maximum}")
    return result


def _optional_path(value: Any) -> Optional[Path]:
    if not value:
        return None
    if not isinstance(value, str):
        raise ConfigError("Path fields must be strings when provided")
    return Path(value)


__all__ = [
    "Config",
    "ConfigError",
    "DemoRecordingConfig",
    "Esp8266Config",
    "HandTrackingConfig",
    "ROI",
    "Resolution",
    "SessionConfig",
    "StepThreshold",
    "VALID_STEP_IDS",
    "VideoCaptureConfig",
    "load_config",
]
