"""ROI calibration CLI with live preview and headless adjustments."""

from __future__ import annotations

import argparse
import logging
import os
import site
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

import yaml

from deltawash_pi.cli._helpers import add_common_args, configure_logging, load_cli_config
from deltawash_pi.config.loader import Config, ROI

LOGGER = logging.getLogger(__name__)


def _add_system_site_packages() -> None:
    if sys.prefix == getattr(sys, "base_prefix", sys.prefix):
        return
    candidates = [
        "/usr/lib/python3/dist-packages",
        f"/usr/lib/python{sys.version_info.major}.{sys.version_info.minor}/dist-packages",
        "/usr/local/lib/python3/dist-packages",
        f"/usr/local/lib/python{sys.version_info.major}.{sys.version_info.minor}/dist-packages",
    ]
    for path in candidates:
        if os.path.isdir(path):
            site.addsitedir(path)

try:  # pragma: no cover - exercised on hardware
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None

_add_system_site_packages()
try:  # pragma: no cover - exercised on hardware
    from picamera2 import Picamera2
except Exception:  # pragma: no cover
    Picamera2 = None
try:  # pragma: no cover - exercised on hardware
    from libcamera import Transform
except Exception:  # pragma: no cover
    Transform = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deltawash-roi-calibrate",
        description="Preview the camera feed with ROI overlay to update config values.",
    )
    add_common_args(parser)
    parser.add_argument(
        "--write-back",
        action="store_true",
        help="Persist updated ROI coordinates to the provided config file",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Skip camera preview and apply the provided coordinate deltas",
    )
    parser.add_argument("--dx", type=int, default=0, help="Move ROI along X axis (headless mode)")
    parser.add_argument("--dy", type=int, default=0, help="Move ROI along Y axis (headless mode)")
    parser.add_argument("--dw", type=int, default=0, help="Adjust ROI width (headless mode)")
    parser.add_argument("--dh", type=int, default=0, help="Adjust ROI height (headless mode)")
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="Deprecated; Picamera2 backend only. Ignored.",
    )
    parser.add_argument(
        "--preview-scale",
        type=float,
        default=1.0,
        help="Scale factor for preview window (use <1.0 for faster X11 display)",
    )
    parser.add_argument(
        "--rotate-180",
        action="store_true",
        help="Rotate the preview 180 degrees (equivalent to --hflip + --vflip)",
    )
    parser.add_argument(
        "--hflip",
        action="store_true",
        help="Apply a horizontal flip to the preview",
    )
    parser.add_argument(
        "--vflip",
        action="store_true",
        help="Apply a vertical flip to the preview",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.verbose)
    config = load_cli_config(args.config)
    if args.headless:
        roi = _run_headless(config, args)
        if args.write_back:
            _persist_roi(args.config, roi)
        return 0

    if cv2 is None:
        raise SystemExit("OpenCV is not available; reinstall with GUI support or use --headless")
    if Picamera2 is None:
        raise SystemExit("Picamera2 is not available; install via apt or use --headless")
    if (args.rotate_180 or args.hflip or args.vflip) and Transform is None:
        raise SystemExit("libcamera Transform unavailable; install libcamera-apps or use --headless")

    return _run_preview(config, args)


@dataclass
class ROIAdjuster:
    roi: ROI
    bounds: Optional[Tuple[int, int]] = None
    min_size: int = 40

    def set_bounds(self, width: int, height: int) -> None:
        self.bounds = (width, height)

    def apply(self, dx: int, dy: int, dw: int, dh: int) -> None:
        self.roi = ROI(
            x=self._clamp(self.roi.x + dx, axis="x"),
            y=self._clamp(self.roi.y + dy, axis="y"),
            width=self._clamp_dimension(self.roi.width + dw, axis="x"),
            height=self._clamp_dimension(self.roi.height + dh, axis="y"),
        )
        self._ensure_within_bounds()

    def _ensure_within_bounds(self) -> None:
        if not self.bounds:
            return
        max_width, max_height = self.bounds
        if self.roi.x + self.roi.width > max_width:
            self.roi = ROI(
                x=max_width - self.roi.width,
                y=self.roi.y,
                width=self.roi.width,
                height=self.roi.height,
            )
        if self.roi.y + self.roi.height > max_height:
            self.roi = ROI(
                x=self.roi.x,
                y=max_height - self.roi.height,
                width=self.roi.width,
                height=self.roi.height,
            )
        self.roi = ROI(
            x=max(0, self.roi.x),
            y=max(0, self.roi.y),
            width=self.roi.width,
            height=self.roi.height,
        )

    def _clamp(self, value: int, *, axis: str) -> int:
        if not self.bounds:
            return value
        limit = self.bounds[0 if axis == "x" else 1]
        return max(0, min(value, limit - self.min_size))

    def _clamp_dimension(self, value: int, *, axis: str) -> int:
        min_size = self.min_size
        if not self.bounds:
            return max(min_size, value)
        limit = self.bounds[0 if axis == "x" else 1]
        return max(min_size, min(value, limit))


def _run_headless(config: Config, args: argparse.Namespace) -> ROI:
    adjuster = ROIAdjuster(config.roi, _resolution_bounds(config))
    adjuster.apply(args.dx, args.dy, args.dw, args.dh)
    roi = adjuster.roi
    LOGGER.info(
        "Headless ROI update -> x=%d y=%d width=%d height=%d",
        roi.x,
        roi.y,
        roi.width,
        roi.height,
    )
    return roi


def _run_preview(config: Config, args: argparse.Namespace) -> int:  # pragma: no cover - requires hardware
    camera = Picamera2()
    resolution = _preview_resolution(config)
    try:
        cam_config = camera.create_video_configuration(
            main={"size": resolution, "format": "RGB888"},
            buffer_count=2,
            queue=False,
            transform=_camera_transform(args),
        )
    except TypeError:
        cam_config = camera.create_video_configuration(
            main={"size": resolution, "format": "RGB888"},
            transform=_camera_transform(args),
        )
    camera.configure(cam_config)
    camera.start()

    adjuster = ROIAdjuster(config.roi)
    saved = False
    try:
        while True:
            frame = camera.capture_array()
            if frame is None:
                LOGGER.error("Camera frame unavailable; exiting preview")
                break
            height, width = frame.shape[:2]
            adjuster.set_bounds(width, height)
            overlay = frame.copy()
            roi = adjuster.roi
            cv2.rectangle(overlay, (roi.x, roi.y), (roi.x + roi.width, roi.y + roi.height), (0, 255, 0), 2)
            cv2.putText(
                overlay,
                "WASD move | J/L width | I/K height | SPACE save | Q quit",
                (10, height - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )
            display_frame = _scale_frame(overlay, args.preview_scale)
            cv2.imshow("ROI Calibrate", display_frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key in _SAVE_KEYS and args.write_back:
                _persist_roi(args.config, adjuster.roi)
                saved = True
                LOGGER.info("ROI saved to %s", args.config)
            elif key in _KEY_BINDINGS:
                dx, dy, dw, dh = _KEY_BINDINGS[key]
                adjuster.apply(dx, dy, dw, dh)
    finally:
        camera.stop()
        camera.close()
        cv2.destroyAllWindows()

    if args.write_back and not saved:
        _persist_roi(args.config, adjuster.roi)
        LOGGER.info("ROI saved to %s", args.config)
    return 0


def _persist_roi(config_path: str, roi: ROI) -> None:
    path = Path(config_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.setdefault("roi", {})
    data["roi"].update({"x": roi.x, "y": roi.y, "width": roi.width, "height": roi.height})
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _resolution_bounds(config: Config) -> Optional[Tuple[int, int]]:
    if not config.resolution:
        return None
    return (config.resolution.width, config.resolution.height)


def _preview_resolution(config: Config) -> Tuple[int, int]:
    if config.resolution:
        return (config.resolution.width, config.resolution.height)
    return (640, 480)


def _camera_transform(args: argparse.Namespace):
    if Transform is None:
        return None
    hflip = args.hflip or args.rotate_180
    vflip = args.vflip or args.rotate_180
    if not (hflip or vflip):
        return None
    return Transform(hflip=hflip, vflip=vflip)


def _scale_frame(frame, scale: float):
    if scale >= 0.99:
        return frame
    if scale <= 0.1:
        scale = 0.1
    height, width = frame.shape[:2]
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)


_SAVE_KEYS = (ord(" "), ord("\r"), ord("\n"))


_KEY_BINDINGS = {
    ord("w"): (0, -5, 0, 0),
    ord("s"): (0, 5, 0, 0),
    ord("a"): (-5, 0, 0, 0),
    ord("d"): (5, 0, 0, 0),
    ord("j"): (0, 0, -5, 0),
    ord("l"): (0, 0, 5, 0),
    ord("i"): (0, 0, 0, -5),
    ord("k"): (0, 0, 0, 5),
    81: (-5, 0, 0, 0),  # left arrow
    82: (0, -5, 0, 0),  # up arrow
    83: (5, 0, 0, 0),   # right arrow
    84: (0, 5, 0, 0),   # down arrow
}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
