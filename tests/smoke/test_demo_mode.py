from __future__ import annotations

import argparse
import io
from pathlib import Path

from deltawash_pi.cli.demo import DemoApp
from deltawash_pi.config.loader import load_config
from deltawash_pi.feedback.status import ConsoleStatusReporter
from deltawash_pi.interpreter.types import StepID


class RecordingStatusReporter(ConsoleStatusReporter):
    def __init__(self, *, output: io.StringIO):
        super().__init__(list(StepID), output=output)
        self.latencies: list[float] = []

    def _record_latency(self, latency: float) -> None:  # type: ignore[override]
        self.latencies.append(latency)


def _demo_args(asset: str = "sample-sequence", *, verify: bool = True) -> argparse.Namespace:
    manifest_path = Path("demos/manifest.json")
    return argparse.Namespace(asset=asset, manifest=str(manifest_path), verify=verify)


def test_demo_mode_status_grid_renders() -> None:
    config = load_config("config/example.yaml")
    buffer = io.StringIO()
    reporter = RecordingStatusReporter(output=buffer)
    app = DemoApp(config, _demo_args(), status_reporter=reporter)
    exit_code = app.run()
    assert exit_code == 0

    output = buffer.getvalue()
    assert "STEP | STATE" in output
    assert "COMPLETED" in output
    assert reporter.latencies, "status reporter should record render latencies"


def test_demo_mode_status_latency_within_budget() -> None:
    config = load_config("config/example.yaml")
    reporter = RecordingStatusReporter(output=io.StringIO())
    app = DemoApp(config, _demo_args(), status_reporter=reporter)
    exit_code = app.run()
    assert exit_code == 0
    assert reporter.latencies, "at least one refresh latency must be recorded"
    assert max(reporter.latencies) <= 0.55, "status refresh exceeded 500 ms budget"
