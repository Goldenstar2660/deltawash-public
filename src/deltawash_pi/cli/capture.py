"""Live capture CLI for WHO steps 2-7 detection.

Uses CNN-only inference - MediaPipe has been eliminated.
"""

from __future__ import annotations

import argparse
import logging
import os
import site
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
import json
from typing import Any, Deque, Dict, Iterator, List, Optional, Sequence, TextIO, Tuple

import cv2
import numpy as np

from deltawash_pi.cli._helpers import add_common_args, configure_logging, load_cli_config
from deltawash_pi.cli._demo_utils import DemoSignalSynthesizer, boost_demo_packet, override_step_durations
from deltawash_pi.cli._recording import RecordingManager
from deltawash_pi.config.loader import Config, HandTrackingConfig, ROI
from deltawash_pi.detectors.runner import build_default_runner
from deltawash_pi.demo.sample_inference import SampleInferenceConfig, SampleInferenceSynthesizer
from deltawash_pi.demo.replay import DemoReplay, load_manifest, summarize_step_durations
from deltawash_pi.feedback.esp8266 import Esp8266Client
from deltawash_pi.feedback.status import ConsoleStatusReporter
from deltawash_pi.interpreter.session_manager import SessionEvent, SessionEventType, SessionManager
from deltawash_pi.interpreter.state_machine import (
    InterpreterEvent,
    InterpreterEventType,
    InterpreterStateMachine,
)
from deltawash_pi.interpreter.types import FramePacket, MotionMetrics, StepID, StepSignal, StepState
from deltawash_pi.logging.sessions import SessionLogger, detect_model_version

LOGGER = logging.getLogger(__name__)


def _add_system_site_packages() -> None:
    """Add system site packages for Picamera2."""
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
        LOGGER.debug("Added system site-packages paths for Picamera2")


_add_system_site_packages()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deltawash-capture",
        description="Capture camera frames, run detectors, and stream interpreter output.",
    )
    add_common_args(parser)
    parser.add_argument(
        "--demo-asset",
        help="Optional deterministic asset id (from demos/manifest.json) to replay instead of camera input",
    )
    parser.add_argument(
        "--demo-manifest",
        default="demos/manifest.json",
        help="Path to demo manifest used with --demo-asset",
    )
    parser.add_argument(
        "--demo-realtime",
        action="store_true",
        help="Sleep between demo frames to simulate real-time playback",
    )
    parser.add_argument(
        "--sample-inference",
        action="store_true",
        help="Use deterministic sample inference from demo annotations (requires --demo-asset)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config without opening camera devices",
    )
    parser.add_argument(
        "--mock-session",
        action="store_true",
        help="Feed synthetic frames through the session manager (used for tests)",
    )
    parser.add_argument(
        "--mock-frames",
        type=int,
        default=60,
        help="Number of frames to emit when --mock-session is enabled",
    )
    parser.add_argument(
        "--max-live-frames",
        type=int,
        help="Optional safety stop when running live capture (otherwise runs until Ctrl-C)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show a live preview window with ROI overlay (requires X11 display)",
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
        help="Rotate the camera feed 180 degrees (equivalent to --hflip + --vflip)",
    )
    parser.add_argument(
        "--hflip",
        action="store_true",
        help="Apply a horizontal flip to the camera feed",
    )
    parser.add_argument(
        "--vflip",
        action="store_true",
        help="Apply a vertical flip to the camera feed",
    )
    parser.add_argument(
        "--status-interval",
        type=float,
        default=1.0,
        help="Seconds between status log lines (0 disables)",
    )
    parser.add_argument(
        "--log-steps",
        action="store_true",
        help="Log the most confident step signal to the terminal",
    )
    parser.add_argument(
        "--log-steps-interval",
        type=float,
        default=0.5,
        help="Seconds between step log lines when --log-steps is enabled",
    )
    parser.add_argument(
        "--export-training-data",
        action="store_true",
        help="Record synchronized landmarks and video for offline labeling",
    )
    parser.add_argument(
        "--export-base-path",
        default="recordings/training_exports",
        help="Base directory for training export session folders",
    )
    parser.add_argument(
        "--export-step",
        help="Optional step label to annotate training exports (e.g., STEP_3)",
    )
    parser.add_argument(
        "--export-orientation",
        default="NONE",
        help="Optional orientation label for training exports",
    )
    parser.add_argument(
        "--export-video-fps",
        type=float,
        default=24.0,
        help="FPS to use for MP4 video written during training exports",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.verbose)
    config = load_cli_config(args.config)
    LOGGER.info("Config loaded (version=%s source=%s)", config.config_version, config.source)

    if args.dry_run:
        LOGGER.info("Dry run complete; camera initialization skipped")
        return 0

    app = CaptureApp(config, args)
    return app.run()


class CaptureApp:
    """Orchestrates frame processing, session gating, and recording."""

    def __init__(self, config: Config, args: argparse.Namespace):
        self._config = config
        self._args = args
        self._recording = RecordingManager(config.demo_recording, config.video_capture)
        self._session_manager = SessionManager(config, self._handle_session_event)
        self._led_client = Esp8266Client(config.esp8266) if config.esp8266.enabled else None
        if config.esp8266.enabled:
            endpoint = config.esp8266.host or config.esp8266.endpoint
            LOGGER.info("ESP8266 LED enabled (host=%s)", endpoint)
            # Send reset signal immediately on startup
            if self._led_client:
                try:
                    self._led_client._reset_leds()
                    LOGGER.info("ESP8266 reset signal sent on startup")
                except Exception as e:
                    LOGGER.warning("Failed to send ESP8266 reset on startup: %s", e)
        else:
            LOGGER.info("ESP8266 LED disabled in config; no LED updates will be sent")
        self._interpreter = InterpreterStateMachine(
            config,
            self._handle_interpreter_event,
            led_client=self._led_client,
        )
        self._status_reporter = ConsoleStatusReporter(list(StepID))
        self._session_logger = SessionLogger()
        self._model_version = detect_model_version()
        self._demo_asset_id = args.demo_asset if args.demo_asset else None
        self._demo_mode = bool(self._demo_asset_id)
        self._last_status_log = 0.0
        self._step_runner = build_default_runner(config)
        self._sample_inference = None
        if args.sample_inference:
            if self._demo_mode:
                self._sample_inference = SampleInferenceSynthesizer(
                    SampleInferenceConfig(dropout_rate=0.0, mislabel_rate=0.0)
                )
            else:
                self._sample_inference = SampleInferenceSynthesizer()
        self._demo_synthesizer = DemoSignalSynthesizer() if self._demo_mode and not args.sample_inference else None
        self._last_step_log = 0.0
        self._last_step_key: Optional[Tuple[str, str]] = None
        self._preview = PreviewDisplay(
            enabled=args.preview,
            roi=config.roi,
            scale=args.preview_scale,
        )
        self._training_exporter: Optional[TrainingDataExporter] = None
        if args.export_training_data:
            self._training_exporter = TrainingDataExporter(
                base_path=args.export_base_path,
                step_label=args.export_step,
                orientation=args.export_orientation,
                video_fps=args.export_video_fps,
            )

    def run(self) -> int:
        try:
            if self._args.sample_inference and not self._args.demo_asset:
                LOGGER.error("--sample-inference requires --demo-asset")
                return 2
            if self._args.mock_session:
                LOGGER.info("Running mock session stream (%d frames)", self._args.mock_frames)
                for packet in self._mock_frame_stream(self._args.mock_frames):
                    self._process_packet(packet)
                LOGGER.info("Mock stream completed")
                return 0
            if self._args.demo_asset:
                return self._run_demo_asset()

            return self._run_live_capture()
        finally:
            self._close_recorders()

    def _process_packet(self, packet: FramePacket) -> None:
        self._preview.update(packet)
        self._session_manager.process_frame(packet)
        signals: Optional[List[StepSignal]] = None
        inference_latency_ms: Optional[float] = None
        needs_signals = self._session_manager.session_active or self._args.log_steps
        if needs_signals:
            if self._demo_synthesizer is not None:
                signals = self._demo_synthesizer.generate(packet)
            else:
                if self._sample_inference:
                    packet.metadata["_disable_demo_hints"] = True
                    packet.metadata["_ml_inference"] = self._sample_inference.infer(packet)
                start_eval = time.perf_counter()
                signals = self._step_runner.evaluate(packet)
                inference_latency_ms = (time.perf_counter() - start_eval) * 1000.0
        if self._session_manager.session_active:
            if signals is not None:
                session_id = self._session_manager.current_session_id
                self._session_logger.record_step_signals(
                    session_id,
                    signals,
                    inference_latency_ms=inference_latency_ms,
                )
                self._interpreter.process_signals(signals, packet.timestamp_ms)
            self._recording.record_frame(self._session_manager.current_session_id, packet)
        if self._training_exporter:
            self._training_exporter.record(packet)
        self._maybe_log_status(packet)
        self._maybe_log_step(packet, signals)

    def _handle_session_event(self, event: SessionEvent) -> None:
        if event.event_type is SessionEventType.STARTED:
            LOGGER.info("Session started (id=%s)", event.session_id)
            self._recording.start_session(event.session_id)
            self._interpreter.start_session(event.session_id, event.timestamp_ms)
            self._status_reporter.start_session(event.session_id)
            self._session_logger.handle_session_started(
                event,
                roi=self._config.roi,
                demo_mode=self._demo_mode,
                demo_asset_id=self._demo_asset_id,
                model_version=self._model_version,
            )
        elif event.event_type is SessionEventType.ENDED:
            LOGGER.info(
                "Session ended (id=%s duration=%sms)",
                event.session_id,
                event.details.get("duration_ms"),
            )
            self._recording.end_session(event.session_id)
            snapshot = self._interpreter.snapshot()
            uncertainties = self._interpreter.uncertainty_events()
            self._session_logger.handle_session_ended(
                event,
                step_statuses=snapshot,
                uncertainty_events=uncertainties,
            )
            self._interpreter.end_session(event.timestamp_ms)
            self._status_reporter.end_session()

    def _handle_interpreter_event(self, event: InterpreterEvent) -> None:
        if event.event_type is InterpreterEventType.STEP_STATE and event.state is StepState.COMPLETED:
            LOGGER.info(
                "Step %s completed (%sms)",
                event.step_id.value if event.step_id else "unknown",
                event.details.get("accumulated_ms"),
            )
        elif event.event_type is InterpreterEventType.UNCERTAINTY:
            LOGGER.debug("Uncertainty event: %s", event.details)
        elif event.event_type is InterpreterEventType.ACTIVE_STEP:
            current = event.details.get("active_step")
            if current:
                LOGGER.debug("Current step: %s", current)
        self._status_reporter.handle_event(event)

    def _run_demo_asset(self) -> int:
        manifest_path = self._args.demo_manifest
        try:
            manifest = load_manifest(manifest_path)
        except Exception as exc:  # pragma: no cover - parse errors exercised via CLI
            LOGGER.error("Failed to load demo manifest (%s): %s", manifest_path, exc)
            return 2

        self._apply_demo_thresholds(manifest, self._args.demo_asset)
        self._prime_demo_session()
        replay = DemoReplay(manifest, self._config)
        LOGGER.info("Streaming demo asset '%s'", self._args.demo_asset)
        for packet in replay.stream_packets(self._args.demo_asset):
            enriched = boost_demo_packet(packet, self._config)
            self._process_packet(enriched)
            if self._args.demo_realtime:
                interval_ms = enriched.metadata.get("demo_frame_interval_ms", 0)
                if isinstance(interval_ms, int) and interval_ms > 0:
                    time.sleep(interval_ms / 1000.0)
        # Note: We intentionally do NOT flush the demo synthesizer.
        # Flushing would artificially complete steps that haven't accumulated
        # enough time according to config's duration_ms thresholds.
        LOGGER.info("Demo asset stream completed")
        self._session_manager.reset()
        self._status_reporter.force_render()
        return 0

    def _apply_demo_thresholds(self, manifest, asset_id: str) -> None:
        """Log demo annotation durations for informational purposes.
        
        Note: We intentionally do NOT override the config's duration_ms thresholds.
        Completion should be based on the config's duration_ms requirements, not the
        annotation durations from the demo asset. This ensures steps only complete
        when they accumulate enough time according to config requirements.
        """
        try:
            asset = manifest.require(asset_id)
        except Exception:
            return
        durations = summarize_step_durations(asset)
        if not durations:
            return
        # Log demo annotation durations for debugging, but use config duration_ms for completion
        pretty = ", ".join(f"{step.value}={ms}ms" for step, ms in sorted(durations.items(), key=lambda item: item[0].value))
        LOGGER.info("Demo annotation durations (informational): %s", pretty)
        # Log config thresholds that will be used for completion
        config_pretty = ", ".join(
            f"{step}={self._config.steps[step].duration_ms}ms"
            for step in sorted(self._config.steps.keys())
        )
        LOGGER.info("Config duration_ms thresholds (used for completion): %s", config_pretty)

    def _prime_demo_session(self) -> None:
        warmup_frames = max(0, self._config.session.start_window_frames)
        if warmup_frames <= 0:
            return
        baseline_motion = MotionMetrics(
            mean_velocity=max(self._config.session.motion_threshold, 0.5),
            relative_motion=max(self._config.session.relative_motion_threshold, 0.3),
        )
        for index in range(warmup_frames):
            packet = FramePacket(
                frame_id=-warmup_frames + index,
                timestamp_ms=-(warmup_frames - index),
                roi=self._config.roi,
                config_version=self._config.config_version,
                motion=baseline_motion,
                landmarks=None,
                metadata={"hand_count": 2, "hands_in_roi": 2},
            )
            self._session_manager.process_frame(packet)

    def _run_live_capture(self) -> int:  # pragma: no cover - hardware path
        try:
            stream = LiveCameraStream(self._config, self._args)
        except RuntimeError as exc:
            LOGGER.error("%s", exc)
            return 2

        processed = 0
        max_frames = self._args.max_live_frames
        LOGGER.info("Live capture started (Ctrl-C to stop)%s",
                    " | frame limit=" + str(max_frames) if max_frames else "")
        try:
            for packet in stream.packets():
                self._process_packet(packet)
                processed += 1
                if max_frames is not None and processed >= max_frames:
                    LOGGER.info("Frame limit reached; stopping capture")
                    break
        except KeyboardInterrupt:
            LOGGER.info("Capture interrupted by user")
        finally:
            stream.close()
            self._preview.close()
        return 0

    def _close_recorders(self) -> None:
        if self._training_exporter:
            self._training_exporter.close()
            self._training_exporter = None

    def _mock_frame_stream(self, total_frames: int) -> Iterator[FramePacket]:
        roi = self._config.roi
        timestamp_ms = 0
        for frame_id in range(total_frames):
            in_roi_phase = 5 <= frame_id < 25
            motion_phase = 5 <= frame_id < 25
            hand_count = 2 if in_roi_phase else 1
            mean_velocity = 0.75 if motion_phase else 0.2
            relative_motion = 0.45 if motion_phase else 0.1
            metadata = {
                "hand_count": hand_count,
                "hands_in_roi": hand_count,
            }
            yield FramePacket(
                frame_id=frame_id,
                timestamp_ms=timestamp_ms,
                roi=roi,
                config_version=self._config.config_version,
                motion=MotionMetrics(mean_velocity=mean_velocity, relative_motion=relative_motion),
                landmarks=None,
                metadata=metadata,
            )
            timestamp_ms += 100

    def _maybe_log_status(self, packet: FramePacket) -> None:
        interval = max(0.0, float(self._args.status_interval))
        if interval == 0.0:
            return
        now = time.monotonic()
        if now - self._last_status_log < interval:
            return
        self._last_status_log = now
        hand_count = packet.metadata.get("hand_count", 0)
        hands_in_roi = packet.metadata.get("hands_in_roi", 0)
        raw_count = packet.metadata.get("hand_count_raw", hand_count)
        raw_in_roi = packet.metadata.get("hands_in_roi_raw", hands_in_roi)
        if raw_count != hand_count or raw_in_roi != hands_in_roi:
            hands_note = f"{hand_count} (raw={raw_count})"
            roi_note = f"{hands_in_roi} (raw={raw_in_roi})"
        else:
            hands_note = str(hand_count)
            roi_note = str(hands_in_roi)
        LOGGER.info(
            "Status: hands=%s in_roi=%s motion=%.3f/%.3f session=%s",
            hands_note,
            roi_note,
            packet.motion.mean_velocity,
            packet.motion.relative_motion,
            "active" if self._session_manager.session_active else "idle",
        )

    def _maybe_log_step(self, packet: FramePacket, signals: Optional[List[StepSignal]]) -> None:
        if not self._args.log_steps:
            return
        interval = max(0.0, float(self._args.log_steps_interval))
        now = time.monotonic()
        if interval > 0.0 and now - self._last_step_log < interval:
            return
        if signals is None:
            signals = self._step_runner.evaluate(packet)
        confident = [sig for sig in signals if sig.is_confident]
        if not confident:
            return
        best = max(confident, key=lambda sig: sig.confidence)
        key = (best.step_id.value, best.orientation.value)
        if key == self._last_step_key and interval > 0.0:
            return
        self._last_step_key = key
        self._last_step_log = now
        LOGGER.info(
            "Step: %s orientation=%s confidence=%.2f",
            best.step_id.value,
            best.orientation.value,
            best.confidence,
        )


class LiveCameraStream:
    """Streams FramePacket objects from Picamera2.
    
    Uses motion-based session detection instead of MediaPipe.
    Hand detection is done entirely by the CNN model.
    """

    def __init__(self, config: Config, args: argparse.Namespace):  # pragma: no cover - hardware path
        self._config = config
        Picamera2 = _import_picamera2()
        if Picamera2 is None:
            raise RuntimeError(
                "Picamera2 is not available; install python3-picamera2 or use --mock-session"
            )
        self._camera = Picamera2()
        resolution = (640, 480)
        if config.resolution:
            resolution = (config.resolution.width, config.resolution.height)
        transform = _camera_transform(args)
        hflip = bool(args.hflip or args.rotate_180)
        vflip = bool(args.vflip or args.rotate_180)
        self._frame_transform = {
            "hflip": hflip,
            "vflip": vflip,
            "applied": transform is not None,
        }
        if transform is None:
            try:
                self._camera_config = self._camera.create_video_configuration(
                    main={"size": resolution, "format": "RGB888"},
                    buffer_count=2,
                    queue=False,
                )
            except TypeError:
                self._camera_config = self._camera.create_video_configuration(
                    main={"size": resolution, "format": "RGB888"},
                )
        else:
            try:
                self._camera_config = self._camera.create_video_configuration(
                    main={"size": resolution, "format": "RGB888"},
                    buffer_count=2,
                    queue=False,
                    transform=transform,
                )
            except TypeError:
                self._camera_config = self._camera.create_video_configuration(
                    main={"size": resolution, "format": "RGB888"},
                    transform=transform,
                )
        self._camera.configure(self._camera_config)
        self._camera.start()
        self._motion = MotionEstimator()
        self._frame_id = 0

    def packets(self) -> Iterator[FramePacket]:  # pragma: no cover - hardware path
        while True:
            frame = self._camera.capture_array()
            if frame is None:
                LOGGER.warning("Camera returned empty frame; continuing")
                continue
            motion = self._motion.compute(frame, self._config.roi)
            timestamp_ms = int(time.time() * 1000)
            
            # Without MediaPipe, we estimate hand presence from motion
            # The CNN model will do the actual hand/gesture classification
            has_motion = motion.mean_velocity > 0.02 or motion.relative_motion > 0.01
            estimated_hands = 2 if has_motion else 0
            
            metadata: Dict[str, Any] = {
                "demo_mode": False,
                "frame_transform": dict(self._frame_transform),
                "hand_count": estimated_hands,
                "hands_in_roi": estimated_hands,
            }
            
            yield FramePacket(
                frame_id=self._frame_id,
                timestamp_ms=timestamp_ms,
                roi=self._config.roi,
                config_version=self._config.config_version,
                motion=motion,
                landmarks=None,  # No MediaPipe landmarks
                image=frame,
                metadata=metadata,
            )
            self._frame_id += 1

    def close(self) -> None:  # pragma: no cover - hardware path
        try:
            self._camera.stop()
            self._camera.close()
        except Exception:
            pass


class MotionEstimator:
    """Computes motion heuristics from ROI grayscale deltas."""

    def __init__(self):
        self._previous_gray: Optional[np.ndarray] = None

    def compute(self, frame: np.ndarray, roi: ROI) -> MotionMetrics:
        x, y, w, h = _clamp_roi(roi, frame.shape)
        roi_frame = frame[y : y + h, x : x + w]
        gray = cv2.cvtColor(roi_frame, cv2.COLOR_RGB2GRAY)
        if self._previous_gray is None:
            self._previous_gray = gray.copy()
            return MotionMetrics(mean_velocity=0.0, relative_motion=0.0)
        diff = cv2.absdiff(gray, self._previous_gray)
        self._previous_gray = gray.copy()
        mean_velocity = float(diff.mean() / 255.0)
        relative_motion = float(diff.std() / 255.0)
        if relative_motion == 0.0 and mean_velocity > 0.0:
            relative_motion = mean_velocity
        return MotionMetrics(
            mean_velocity=_clamp_unit(mean_velocity),
            relative_motion=_clamp_unit(relative_motion),
        )


def _clamp_roi(roi: ROI, frame_shape) -> Tuple[int, int, int, int]:
    height, width = frame_shape[:2]
    x = max(0, min(roi.x, width - 1))
    y = max(0, min(roi.y, height - 1))
    w = max(1, min(roi.width, width - x))
    h = max(1, min(roi.height, height - y))
    return x, y, w, h


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def _import_picamera2():  # pragma: no cover - import helper
    try:
        from picamera2 import Picamera2
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    return Picamera2


def _camera_transform(args: argparse.Namespace):
    try:
        from libcamera import Transform
    except Exception:  # pragma: no cover - optional dependency
        return None
    hflip = args.hflip or args.rotate_180
    vflip = args.vflip or args.rotate_180
    if not (hflip or vflip):
        return None
    return Transform(hflip=hflip, vflip=vflip)


class PreviewDisplay:
    """Optional live preview window with ROI overlay."""

    def __init__(self, *, enabled: bool, roi: ROI, scale: float):
        self._enabled = enabled
        self._roi = roi
        self._scale = scale
        if self._enabled and cv2 is None:
            raise RuntimeError("OpenCV is not available; disable --preview or reinstall with GUI support")

    def update(self, packet: FramePacket) -> None:
        if not self._enabled or packet.image is None:
            return
        frame = packet.image
        overlay = frame.copy()
        roi = self._roi
        cv2.rectangle(
            overlay,
            (roi.x, roi.y),
            (roi.x + roi.width, roi.y + roi.height),
            (0, 255, 0),
            2,
        )
        # Display motion info (hands estimated from CNN, not MediaPipe)
        motion_vel = packet.motion.mean_velocity if packet.motion else 0
        motion_rel = packet.motion.relative_motion if packet.motion else 0
        text = f"motion={motion_vel:.2f}/{motion_rel:.2f}"
        cv2.putText(
            overlay,
            text,
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        display = _scale_frame(overlay, self._scale)
        cv2.imshow("DeltaWash Capture", display)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            raise KeyboardInterrupt()

    def close(self) -> None:
        if self._enabled:
            cv2.destroyAllWindows()


def _scale_frame(frame: np.ndarray, scale: float) -> np.ndarray:
    if scale >= 0.99:
        return frame
    if scale <= 0.1:
        scale = 0.1
    height, width = frame.shape[:2]
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)


class TrainingDataExporter:
    """Save synchronized landmark JSONL + MP4 video sessions for offline labeling."""

    def __init__(
        self,
        *,
        base_path: str,
        step_label: Optional[str],
        orientation: Optional[str],
        video_fps: float,
    ) -> None:
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        self._session_dir = self._next_session_dir(timestamp)
        self._session_dir.mkdir(parents=True, exist_ok=False)
        self._landmark_path = self._session_dir / "landmarks.jsonl"
        self._video_path = self._session_dir / "video.mp4"
        self._landmark_handle: TextIO | None = self._landmark_path.open("w", encoding="utf-8")
        self._video_writer = None
        self._video_fps = max(1.0, float(video_fps))
        self._start_ts_ms: Optional[int] = None
        self._step_label = step_label
        self._orientation = orientation or "NONE"
        self._frame_count = 0
        self._warned_missing_image = False
        LOGGER.info(
            "Training export session created at %s (step=%s orientation=%s)",
            self._session_dir,
            self._step_label,
            self._orientation,
        )

    def record(self, packet: FramePacket) -> None:
        if self._start_ts_ms is None:
            self._start_ts_ms = packet.timestamp_ms
        elapsed_s = max(0.0, (packet.timestamp_ms - self._start_ts_ms) / 1000.0)
        left_hand = self._serialize_hand(packet, "LEFT")
        right_hand = self._serialize_hand(packet, "RIGHT")
        payload = {
            "timestamp_s": elapsed_s,
            "step_id": self._step_label,
            "orientation": self._orientation,
            "left_hand": left_hand,
            "right_hand": right_hand,
        }
        if self._landmark_handle is None:
            raise RuntimeError("Training exporter is already closed; cannot record new frames")
        self._landmark_handle.write(json.dumps(payload) + "\n")
        self._record_video_frame(packet)

    def close(self) -> None:
        if self._landmark_handle is not None:
            self._landmark_handle.close()
            self._landmark_handle = None
        if self._video_writer is not None:
            self._video_writer.release()
            self._video_writer = None
        if self._frame_count == 0:
            LOGGER.warning(
                "Training exporter finalized session %s but recorded zero frames",
                self._session_dir,
            )
        else:
            LOGGER.info(
                "Training exporter finalized session %s (frames=%d)",
                self._session_dir,
                self._frame_count,
            )

    def _serialize_hand(self, packet: FramePacket, label: str) -> Optional[Dict[str, Any]]:
        handedness = packet.metadata.get("handedness") or []
        target = next((h for h in handedness if h.get("label") == label), None)
        if target is None:
            return None
        index = int(target.get("index", -1))
        if packet.landmarks is None or index < 0 or index >= len(packet.landmarks):
            return None
        hand_landmarks = packet.landmarks[index].landmark
        coords = [
            [float(lm.x), float(lm.y), float(getattr(lm, "z", 0.0))]
            for lm in hand_landmarks
        ]
        return {
            "landmarks": coords,
            "confidence": float(target.get("confidence", 0.0)),
        }

    def _record_video_frame(self, packet: FramePacket) -> None:
        frame = packet.image
        if frame is None:
            if not self._warned_missing_image:
                LOGGER.warning(
                    "Training exporter: packet missing image data; video may be incomplete"
                )
                self._warned_missing_image = True
            return
        self._ensure_video_writer(frame)
        if self._video_writer is None:
            return
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        else:
            bgr = frame
        self._video_writer.write(bgr)
        self._frame_count += 1

    def _ensure_video_writer(self, frame) -> None:
        if self._video_writer is not None:
            return
        height, width = frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(
            str(self._video_path),
            fourcc,
            self._video_fps,
            (width, height),
        )
        if not writer.isOpened():
            raise RuntimeError(f"Failed to open training export video writer at {self._video_path}")
        self._video_writer = writer
        LOGGER.info("Training exporter writing MP4 video to %s", self._video_path)

    def _next_session_dir(self, timestamp: str) -> Path:
        candidate = self._base_path / timestamp
        suffix = 1
        while candidate.exists():
            candidate = self._base_path / f"{timestamp}-{suffix:02d}"
            suffix += 1
        return candidate


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
