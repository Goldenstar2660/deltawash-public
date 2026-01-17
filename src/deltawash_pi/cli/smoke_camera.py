"""Smoke-test CLI for camera capture and latency benchmarking."""

from __future__ import annotations

import argparse
import logging
import os
import site
import sys
import time
from statistics import mean
from typing import Dict, List, Sequence

import numpy as np

from deltawash_pi.cli._helpers import add_common_args, configure_logging, load_cli_config

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
    added = False
    for path in candidates:
        if os.path.isdir(path):
            site.addsitedir(path)
            added = True
    if added:
        LOGGER.debug("Added system site-packages paths for optional camera backends")


_add_system_site_packages()
try:  # pragma: no cover - exercised on hardware
    from picamera2 import Picamera2
except Exception:  # pragma: no cover - optional dependency guard
    Picamera2 = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deltawash-smoke-camera",
        description="Measure capture -> detector latency to guard the 200 ms budget.",
    )
    add_common_args(parser)
    parser.add_argument(
        "--frames",
        type=int,
        default=200,
        help="Number of frames to sample when running the benchmark",
    )
    parser.add_argument(
        "--latency-threshold-ms",
        type=int,
        default=200,
        help="Fail the benchmark when latency exceeds this threshold (mean & p95)",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="Deprecated; Picamera2 backend only. Ignored.",
    )
    parser.add_argument(
        "--backend",
        choices=("picamera2",),
        default="picamera2",
        help="Camera backend to use (Picamera2 only)",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=5,
        help="Frames to read and discard before benchmarking",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run the benchmark against a synthetic workload for CI environments",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.verbose)
    config = load_cli_config(args.config)
    LOGGER.info(
        "Config loaded (version=%s); frames=%d latency-threshold=%d ms",
        config.config_version,
        args.frames,
        args.latency_threshold_ms,
    )

    latencies = (
        _run_mock_benchmark(args.frames)
        if args.mock
        else _run_camera_benchmark(args.frames, args.camera_index, args.backend, args.warmup_frames)
    )

    if not latencies:
        LOGGER.error("No frames processed during benchmark")
        return 2

    summary = _summarize(latencies)
    LOGGER.info(
        "Frames=%d mean=%.1f ms p95=%.1f ms approx_FPS=%.1f",
        len(latencies),
        summary["mean"],
        summary["p95"],
        summary["fps"],
    )

    threshold = args.latency_threshold_ms
    if summary["mean"] > threshold or summary["p95"] > threshold:
        LOGGER.error(
            "Latency budget exceeded (threshold=%d ms). mean=%.1f ms p95=%.1f ms",
            threshold,
            summary["mean"],
            summary["p95"],
        )
        return 1

    LOGGER.info("Latency target upheld")
    return 0


def _run_mock_benchmark(frame_count: int) -> List[float]:
    latencies: List[float] = []
    for _ in range(frame_count):
        start = time.perf_counter()
        time.sleep(0.005)  # emulate capture delay
        _simulate_detector(None)
        latencies.append((time.perf_counter() - start) * 1000.0)
    return latencies


def _run_camera_benchmark(
    frame_count: int, camera_index: int, backend: str, warmup_frames: int
) -> List[float]:  # pragma: no cover - hardware path
    if backend != "picamera2":
        raise SystemExit("Only Picamera2 backend is supported")
    if Picamera2 is None:
        raise SystemExit("Picamera2 is not available; install via apt and re-run")
    LOGGER.info("Using Picamera2 backend")
    return _run_picamera2_benchmark(frame_count, warmup_frames)


def _run_picamera2_benchmark(frame_count: int, warmup_frames: int) -> List[float]:  # pragma: no cover - hardware path
    camera = Picamera2()
    config = camera.create_video_configuration(main={"size": (640, 480), "format": "RGB888"})
    camera.configure(config)
    camera.start()
    latencies: List[float] = []
    try:
        warmup_success = 0
        for _ in range(max(warmup_frames, 0)):
            frame = camera.capture_array()
            if frame is not None:
                warmup_success += 1
        if warmup_frames > 0 and warmup_success == 0:
            raise RuntimeError("Picamera2 produced no frames during warmup")

        for _ in range(frame_count):
            start = time.perf_counter()
            frame = camera.capture_array()
            if frame is None:
                LOGGER.warning("Picamera2 returned no frame; stopping benchmark")
                break
            _simulate_detector(frame)
            latencies.append((time.perf_counter() - start) * 1000.0)
    finally:
        camera.stop()
        camera.close()
    return latencies


def _simulate_detector(frame) -> float:
    if frame is None or np is None:
        time.sleep(0.001)
        return 0.0
    # Minimal workload to approximate detector math without MediaPipe.
    _ = float(np.mean(frame))
    return _


def _summarize(latencies: List[float]) -> Dict[str, float]:
    arr = np.array(latencies, dtype=float)
    mean_latency = float(mean(latencies))
    p95_latency = float(np.percentile(arr, 95))
    approx_fps = 1000.0 / mean_latency if mean_latency else 0.0
    return {"mean": mean_latency, "p95": p95_latency, "fps": approx_fps}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
