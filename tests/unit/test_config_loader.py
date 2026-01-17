from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltawash_pi.config.loader import (
    VALID_STEP_IDS,
    ConfigError,
    load_config,
)


def _base_config_dict() -> dict:
    steps = {
        step_id: {"duration_ms": 3000, "confidence_min": 0.7}
        for step_id in VALID_STEP_IDS
    }
    return {
        "config_version": "test-001",
        "resolution": {"width": 640, "height": 480},
        "roi": {"x": 100, "y": 50, "width": 200, "height": 200},
        "session": {
            "motion_threshold": 0.5,
            "relative_motion_threshold": 0.4,
            "start_window_frames": 5,
            "stop_timeout_ms": 1500,
            "min_hands": 2,
            "require_motion": True,
        },
        "steps": steps,
        "esp8266": {"enabled": False},
        "video_capture": {"enabled": False},
        "demo_recording": {"enabled": False},
    }


def _write_config(tmp_path: Path, data: dict) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return config_path


def test_load_config_success(tmp_path: Path) -> None:
    data = _base_config_dict()
    cfg = load_config(_write_config(tmp_path, data))

    assert cfg.config_version == "test-001"
    assert cfg.roi.width == 200
    assert cfg.session.motion_threshold == pytest.approx(0.5)
    assert set(cfg.steps.keys()) == set(VALID_STEP_IDS)


def test_missing_step_entry_raises(tmp_path: Path) -> None:
    data = _base_config_dict()
    data["steps"].pop("STEP_4")
    with pytest.raises(ConfigError) as exc:
        load_config(_write_config(tmp_path, data))
    assert "STEP_4" in str(exc.value)


def test_video_capture_retention_conflict(tmp_path: Path) -> None:
    data = _base_config_dict()
    captures_dir = tmp_path / "captures"
    data["video_capture"] = {
        "enabled": True,
        "storage_path": str(captures_dir),
        "retention_seconds": 60,
        "max_sessions": 3,
    }
    with pytest.raises(ConfigError):
        load_config(_write_config(tmp_path, data))


def test_demo_recording_requires_absolute_path(tmp_path: Path) -> None:
    data = _base_config_dict()
    data["demo_recording"] = {"enabled": True, "output_path": "relative/path"}
    with pytest.raises(ConfigError):
        load_config(_write_config(tmp_path, data))
