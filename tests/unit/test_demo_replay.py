from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from deltawash_pi.config.loader import load_config
from deltawash_pi.demo.replay import DemoReplay, ManifestError, load_manifest
from deltawash_pi.interpreter.types import StepID


def _write_config(tmp_path: Path) -> Path:
    config = {
        "config_version": "test-demo",
        "roi": {"x": 0, "y": 0, "width": 100, "height": 100},
        "session": {
            "motion_threshold": 0.3,
            "relative_motion_threshold": 0.2,
            "start_window_frames": 3,
            "stop_timeout_ms": 1000,
        },
        "steps": {
            step.value: {"duration_ms": 3000, "confidence_min": 0.7}
            for step in StepID
        },
        "esp8266": {"enabled": False},
        "video_capture": {"enabled": False},
        "demo_recording": {"enabled": False},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def _write_manifest(tmp_path: Path) -> Path:
    manifest = {
        "version": "0.1.0",
        "assets": [
            {
                "id": "sample",
                "file": "sample.npz",
                "fps": 25.0,
                "total_frames": 5,
                "roi": {"x": 10, "y": 5, "width": 80, "height": 90},
                "annotations": [
                    {
                        "step_id": "STEP_2",
                        "orientation": "NONE",
                        "start_ms": 0,
                        "end_ms": 3000,
                    }
                ],
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_load_manifest_parses_assets(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    manifest = load_manifest(manifest_path)
    asset = manifest.require("sample")

    assert asset.fps == pytest.approx(25.0)
    assert asset.annotations[0].step_id is StepID.STEP_2
    assert asset.roi is not None
    assert asset.roi.width == 80


def test_stream_packets_emits_expected_count(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))
    manifest = load_manifest(_write_manifest(tmp_path))
    replay = DemoReplay(manifest, config)

    packets = list(replay.stream_packets("sample"))

    assert len(packets) == 5
    assert packets[0].metadata["asset_id"] == "sample"
    assert packets[-1].frame_id == 4


def test_missing_manifest_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        load_manifest(tmp_path / "missing.json")
