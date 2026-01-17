from __future__ import annotations

from pathlib import Path

from deltawash_pi.cli import capture

from tests.unit.test_config_loader import _base_config_dict, _write_config


def _write_capture_config(
    tmp_path: Path,
    *,
    demo_enabled: bool = False,
    video_enabled: bool = False,
    video_max_sessions: int = 0,
) -> tuple[Path, Path, Path]:
    data = _base_config_dict()
    demo_dir = (tmp_path / "demo_frames").resolve()
    video_dir = (tmp_path / "video_storage").resolve()
    data["demo_recording"] = {
        "enabled": demo_enabled,
        "output_path": str(demo_dir),
    }
    data["video_capture"] = {
        "enabled": video_enabled,
        "storage_path": str(video_dir),
        "retention_seconds": 0,
        "max_sessions": video_max_sessions,
    }
    config_path = _write_config(tmp_path, data)
    return config_path, demo_dir, video_dir


def _run_capture(config_path: Path, frames: int = 60) -> int:
    return capture.main([
        "--config",
        str(config_path),
        "--mock-session",
        "--mock-frames",
        str(frames),
    ])


def test_default_capture_creates_no_artifacts(tmp_path: Path) -> None:
    config_path, demo_dir, video_dir = _write_capture_config(tmp_path)

    assert _run_capture(config_path) == 0
    assert not demo_dir.exists()
    assert not video_dir.exists()


def test_demo_recording_writes_frames(tmp_path: Path) -> None:
    config_path, demo_dir, _ = _write_capture_config(tmp_path, demo_enabled=True)

    assert _run_capture(config_path, frames=40) == 0

    assert demo_dir.exists()
    session_dirs = [path for path in demo_dir.iterdir() if path.is_dir()]
    assert len(session_dirs) == 1
    frame_files = list(session_dirs[0].glob("*.ppm"))
    assert frame_files, "Expected annotated frames when demo recording is enabled"


def test_video_capture_retention_limits_sessions(tmp_path: Path) -> None:
    config_path, _, video_dir = _write_capture_config(
        tmp_path,
        video_enabled=True,
        video_max_sessions=1,
    )

    assert _run_capture(config_path) == 0
    assert video_dir.exists()
    first_run_files = list(video_dir.glob("*.txt"))
    assert len(first_run_files) == 1

    assert _run_capture(config_path) == 0
    second_run_files = list(video_dir.glob("*.txt"))
    assert len(second_run_files) == 1
    assert first_run_files[0] not in second_run_files
