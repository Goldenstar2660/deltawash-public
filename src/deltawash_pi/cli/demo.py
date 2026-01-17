"""Deterministic demo CLI that replays curated assets through the pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional, Sequence

from deltawash_pi.cli._demo_utils import DemoSignalSynthesizer, boost_demo_packet, override_step_durations
from deltawash_pi.cli._helpers import add_common_args, configure_logging, load_cli_config
from deltawash_pi.config.loader import Config
from deltawash_pi.demo.replay import DemoReplay, ManifestError, load_manifest, summarize_step_durations
from deltawash_pi.detectors.runner import build_default_runner
from deltawash_pi.feedback.esp8266 import Esp8266Client
from deltawash_pi.feedback.status import ConsoleStatusReporter
from deltawash_pi.interpreter.session_manager import SessionEvent, SessionEventType, SessionManager
from deltawash_pi.interpreter.state_machine import (
    InterpreterEvent,
    InterpreterEventType,
    InterpreterStateMachine,
)
from deltawash_pi.interpreter.types import FramePacket, MotionMetrics, StepID, StepOrientation, StepState

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deltawash-demo",
        description="Replay deterministic demo assets through the interpreter pipeline.",
    )
    add_common_args(parser)
    parser.add_argument(
        "--asset",
        required=True,
        help="Asset ID or file path listed in the demo manifest",
    )
    parser.add_argument(
        "--manifest",
        default="demos/manifest.json",
        help="Path to the deterministic demo manifest (default: %(default)s)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Enable invariant checks comparing interpreter output against annotations",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.verbose)
    config = load_cli_config(args.config)
    LOGGER.info("Config loaded (version=%s)", config.config_version)

    try:
        app = DemoApp(config, args)
    except ManifestError as exc:
        LOGGER.error("Failed to load demo manifest: %s", exc)
        return 2
    return app.run()


class DemoApp:
    """Coordinates deterministic demo replay for validation and demos."""

    def __init__(
        self,
        config: Config,
        args: argparse.Namespace,
        *,
        status_reporter: Optional[ConsoleStatusReporter] = None,
    ) -> None:
        self._config = config
        self._args = args
        self._manifest = load_manifest(args.manifest)
        self._session_manager = SessionManager(config, self._handle_session_event)
        self._led_client = Esp8266Client(config.esp8266) if config.esp8266.enabled else None
        self._interpreter = InterpreterStateMachine(
            config,
            self._handle_interpreter_event,
            led_client=self._led_client,
        )
        self._status_reporter = status_reporter or ConsoleStatusReporter(list(StepID))
        self._detector_runner = build_default_runner(config)
        self._signal_synthesizer = DemoSignalSynthesizer()

    def run(self) -> int:
        try:
            asset_id = self._resolve_asset_identifier(self._args.asset)
        except ManifestError as exc:
            LOGGER.error("%s", exc)
            return 2

        self._apply_demo_thresholds(asset_id)
        replay = DemoReplay(self._manifest, self._config)
        LOGGER.info("Streaming demo asset '%s'", asset_id)
        self._prime_session()
        for packet in replay.stream_packets(asset_id):
            enriched = boost_demo_packet(packet, self._config)
            self._process_packet(enriched)
        # Note: We intentionally do NOT flush the demo synthesizer.
        # Flushing would artificially complete steps that haven't accumulated
        # enough time according to config's duration_ms thresholds.
        self._session_manager.reset()
        LOGGER.info("Demo asset complete")

        if self._args.verify:
            if not self._verify_asset(asset_id):
                LOGGER.error("Demo verification failed for asset '%s'", asset_id)
                return 3
            LOGGER.info("Demo verification passed for asset '%s'", asset_id)
        return 0

    def _apply_demo_thresholds(self, asset_id: str) -> None:
        """Log demo annotation durations for informational purposes.
        
        Note: We intentionally do NOT override the config's duration_ms thresholds.
        Completion should be based on the config's duration_ms requirements, not the
        annotation durations from the demo asset. This ensures steps only complete
        when they accumulate enough time according to config requirements.
        """
        asset = self._manifest.require(asset_id)
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

    def _process_packet(self, packet: FramePacket) -> None:
        self._session_manager.process_frame(packet)
        if not self._session_manager.session_active:
            return
        signals = self._signal_synthesizer.generate(packet)
        if not signals:
            signals = self._detector_runner.evaluate(packet)
        self._interpreter.process_signals(signals, packet.timestamp_ms)

    def _prime_session(self) -> None:
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

    def _handle_session_event(self, event: SessionEvent) -> None:
        if event.event_type is SessionEventType.STARTED:
            LOGGER.info("Session started (id=%s)", event.session_id)
            self._interpreter.start_session(event.session_id, event.timestamp_ms)
            self._status_reporter.start_session(event.session_id)
        elif event.event_type is SessionEventType.ENDED:
            LOGGER.info("Session ended (id=%s duration=%sms)", event.session_id, event.details.get("duration_ms"))
            self._interpreter.end_session(event.timestamp_ms)
            self._status_reporter.end_session()

    def _handle_interpreter_event(self, event: InterpreterEvent) -> None:
        if event.event_type is InterpreterEventType.STEP_STATE and event.state is StepState.COMPLETED:
            LOGGER.info(
                "Step %s completed (%sms)",
                event.step_id.value if event.step_id else "unknown",
                event.details.get("accumulated_ms"),
            )
        self._status_reporter.handle_event(event)

    def _resolve_asset_identifier(self, value: str) -> str:
        if value in self._manifest.assets:
            return value
        candidate = Path(value).expanduser().resolve()
        for asset_id, asset in self._manifest.assets.items():
            if asset.path == candidate:
                return asset_id
        raise ManifestError(
            f"Asset '{value}' not found. Provide an asset id from {self._args.manifest} or a matching file path."
        )

    def _verify_asset(self, asset_id: str) -> bool:
        """Verify that steps completed based on config duration_ms thresholds.
        
        A step should only complete if its annotation duration >= config's duration_ms.
        """
        asset = self._manifest.require(asset_id)
        snapshot = {status.step_id: status for status in self._interpreter.snapshot()}
        
        # Calculate annotation durations per step
        annotation_durations: dict[StepID, int] = {}
        for annotation in asset.annotations:
            duration = annotation.end_ms - annotation.start_ms
            annotation_durations[annotation.step_id] = (
                annotation_durations.get(annotation.step_id, 0) + duration
            )
        
        last_orientation = {}
        for annotation in asset.annotations:
            last_orientation[annotation.step_id] = annotation.orientation

        errors = []
        for step_id, annotation_duration in annotation_durations.items():
            status = snapshot.get(step_id)
            config_threshold = self._config.steps.get(step_id.value)
            required_ms = config_threshold.duration_ms if config_threshold else 0
            
            should_complete = annotation_duration >= required_ms
            did_complete = status is not None and status.state is StepState.COMPLETED
            
            if should_complete and not did_complete:
                errors.append(
                    f"Step {step_id.value} should have completed "
                    f"(annotation={annotation_duration}ms >= required={required_ms}ms) but didn't"
                )
            elif not should_complete and did_complete:
                errors.append(
                    f"Step {step_id.value} should NOT have completed "
                    f"(annotation={annotation_duration}ms < required={required_ms}ms) but did"
                )
            
            if did_complete:
                orientation = last_orientation.get(step_id)
                if orientation and orientation is not StepOrientation.NONE:
                    if status.orientation != orientation:
                        errors.append(
                            f"Step {step_id.value} orientation mismatch "
                            f"(expected {orientation.value}, got {status.orientation.value})"
                        )

        # Check for unexpected completions of non-annotated steps
        annotated_steps = set(annotation_durations.keys())
        for step, status in snapshot.items():
            if step not in annotated_steps and status.state is StepState.COMPLETED:
                errors.append(f"Step {step.value} unexpectedly completed during demo replay")

        if errors:
            for error in errors:
                LOGGER.error(error)
            return False
        return True


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
