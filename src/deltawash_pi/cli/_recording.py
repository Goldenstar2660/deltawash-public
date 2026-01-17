"""Recording helpers for capture CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import time

from deltawash_pi.config.loader import DemoRecordingConfig, VideoCaptureConfig
from deltawash_pi.interpreter.types import FramePacket


@dataclass
class RecordingContext:
    demo_dir: Optional[Path] = None
    video_path: Optional[Path] = None


class RecordingManager:
    """Handles demo frame exports and video capture retention."""

    def __init__(self, demo_cfg: DemoRecordingConfig, video_cfg: VideoCaptureConfig):
        self._demo_cfg = demo_cfg
        self._video_cfg = video_cfg
        self._sessions: Dict[str, RecordingContext] = {}

    def start_session(self, session_id: str) -> None:
        context = RecordingContext()
        if self._demo_cfg.enabled and self._demo_cfg.output_path:
            base = Path(self._demo_cfg.output_path)
            base.mkdir(parents=True, exist_ok=True)
            session_dir = base / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            context.demo_dir = session_dir
        if self._video_cfg.enabled and self._video_cfg.storage_path:
            storage = Path(self._video_cfg.storage_path)
            storage.mkdir(parents=True, exist_ok=True)
            video_file = storage / f"{session_id}.txt"
            video_file.touch(exist_ok=True)
            context.video_path = video_file
        self._sessions[session_id] = context

    def record_frame(self, session_id: Optional[str], packet: FramePacket) -> None:
        if not session_id:
            return
        context = self._sessions.get(session_id)
        if context is None:
            return
        if context.demo_dir is not None:
            frame_path = context.demo_dir / f"frame_{packet.frame_id:06d}.ppm"
            _write_placeholder_ppm(frame_path, packet)
        if context.video_path is not None:
            with context.video_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{packet.timestamp_ms},{packet.metadata.get('hand_count', 0)}\n")

    def end_session(self, session_id: str) -> None:
        context = self._sessions.pop(session_id, None)
        if context and context.video_path and self._video_cfg.enabled:
            self._apply_retention()

    def _apply_retention(self) -> None:
        storage_path = self._video_cfg.storage_path
        if not storage_path:
            return
        storage = Path(storage_path)
        if self._video_cfg.retention_seconds:
            deadline = time.time() - self._video_cfg.retention_seconds
            for artifact in storage.glob("*.txt"):
                if artifact.stat().st_mtime < deadline:
                    artifact.unlink(missing_ok=True)
        elif self._video_cfg.max_sessions:
            artifacts = sorted(storage.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
            keep = self._video_cfg.max_sessions
            for extra in artifacts[keep:]:
                extra.unlink(missing_ok=True)


def _write_placeholder_ppm(path: Path, packet: FramePacket) -> None:
    color_value = min(255, 50 + (packet.frame_id % 200))
    content = (
        "P3\n"
        "1 1\n"
        "255\n"
        f"{color_value} {255 - color_value} 128\n"
    )
    path.write_text(content, encoding="ascii")


__all__ = ["RecordingManager"]
