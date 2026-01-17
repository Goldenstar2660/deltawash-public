"""Analytics CLI for session summaries and accuracy checks."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Sequence

from deltawash_pi.cli._helpers import add_common_args, configure_logging, load_cli_config
from deltawash_pi.demo.replay import DemoManifest, load_manifest
from deltawash_pi.logging.aggregates import (
    load_session_records,
    merge_accuracy,
    persist_summary,
    summarize_records,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class SummarizeArgs:
    logs: Path
    out: Path


@dataclass
class AccuracyArgs:
    manifest: Path
    logs: Path
    out: Path
    threshold: float


@dataclass(frozen=True)
class AccuracyReport:
    value: Optional[float]
    threshold: float
    sessions: int
    correct: int
    expected: int
    assets: Dict[str, Dict[str, object]]
    generated_ts: str

    @property
    def passed(self) -> bool:
        return self.value is not None and self.value >= self.threshold

    def to_section(self) -> Dict[str, object]:
        return {
            "generated_ts": self.generated_ts,
            "threshold": self.threshold,
            "value": self.value,
            "status": "pass" if self.passed else "fail",
            "sessions_evaluated": self.sessions,
            "steps_correct": self.correct,
            "steps_expected": self.expected,
            "assets": self.assets,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deltawash-analytics",
        description="Summarize session logs or run accuracy checks on demo datasets.",
    )
    add_common_args(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    summarize = subparsers.add_parser("summarize", help="Aggregate session logs into summary metrics")
    summarize.add_argument(
        "--logs",
        default="logs/sessions",
        help="Directory containing JSONL session logs",
    )
    summarize.add_argument(
        "--out",
        default="logs/aggregates/summary.json",
        help="Path to write the aggregate summary JSON",
    )

    accuracy = subparsers.add_parser("accuracy", help="Compute accuracy on labeled demo assets")
    accuracy.add_argument(
        "--manifest",
        default="demos/manifest.json",
        help="Manifest describing the labeled demo subset",
    )
    accuracy.add_argument(
        "--logs",
        default="logs/sessions",
        help="Directory containing prior session logs",
    )
    accuracy.add_argument(
        "--out",
        default="logs/aggregates/summary.json",
        help="Summary JSON file to update with accuracy results",
    )
    accuracy.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Minimum acceptable accuracy before failing (default: %(default)s)",
    )

    return parser


def _handle_summarize(args: SummarizeArgs) -> int:
    records = load_session_records(args.logs)
    summary = summarize_records(records)
    persist_summary(summary, out_path=args.out)
    _print_summary(summary)
    return 0


def _handle_accuracy(args: AccuracyArgs) -> int:
    manifest = load_manifest(args.manifest)
    records = load_session_records(args.logs)
    report = _compute_accuracy_report(manifest, records, threshold=args.threshold)
    if report.value is None:
        LOGGER.error("No demo-mode sessions with recognized assets were found in %s", args.logs)
        return 2
    merge_accuracy(args.out, report.to_section())
    LOGGER.info(
        "Accuracy %.2f%% (%d/%d steps) across %d session(s)",
        report.value * 100.0,
        report.correct,
        report.expected,
        report.sessions,
    )
    for asset_id, details in sorted(report.assets.items()):
        accuracy = details.get("accuracy")
        LOGGER.info(
            "  Asset %s: %.2f%% over %d session(s)",
            asset_id,
            (accuracy or 0.0) * 100.0,
            details.get("sessions", 0),
        )
    return 0 if report.passed else 3


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.verbose)
    config = load_cli_config(args.config)
    LOGGER.info("Config loaded (version=%s)", config.config_version)

    exit_code = 0
    if args.command == "summarize":
        exit_code = _handle_summarize(
            SummarizeArgs(logs=Path(args.logs), out=Path(args.out))
        )
    elif args.command == "accuracy":
        exit_code = _handle_accuracy(
            AccuracyArgs(
                manifest=Path(args.manifest),
                logs=Path(args.logs),
                out=Path(args.out),
                threshold=args.threshold,
            )
        )
    else:  # pragma: no cover
        parser.error(f"Unknown command: {args.command}")

    return exit_code


def _print_summary(summary) -> None:
    LOGGER.info("Sessions summarized: %d", summary.sessions_count)
    if summary.sessions_count == 0:
        LOGGER.warning("No session logs found; summary is empty")
        return
    LOGGER.info("Most missed step: %s", summary.most_missed_step or "n/a")
    LOGGER.info("Model usage rate: %.2f%%", summary.model_usage_rate * 100.0)
    if summary.avg_model_confidence is not None:
        LOGGER.info("Avg model confidence: %.2f", summary.avg_model_confidence)
    if summary.avg_inference_time_ms is not None:
        LOGGER.info("Avg inference latency: %.2f ms", summary.avg_inference_time_ms)
    LOGGER.info("Average step durations (ms): %s", summary.average_step_times_ms)
    LOGGER.info("Uncertainty events: %s", summary.uncertainty_frequency)
    LOGGER.info("Fallback events: %s", summary.fallback_frequency)


def _compute_accuracy_report(
    manifest: DemoManifest,
    records: Sequence[Dict[str, object]],
    *,
    threshold: float,
) -> AccuracyReport:
    expectations = _build_asset_expectations(manifest)
    per_asset: Dict[str, Dict[str, object]] = {}
    sessions = 0
    total_correct = 0
    total_expected = 0

    for record in records:
        if not record.get("demo_mode"):
            continue
        asset_id = record.get("demo_asset_id")
        if not isinstance(asset_id, str):
            continue
        expected_steps = expectations.get(asset_id)
        if not expected_steps:
            LOGGER.debug("Skipping session %s with unknown asset %s", record.get("session_id"), asset_id)
            continue
        status_map = {
            str(status.get("step_id")): status
            for status in record.get("step_statuses", [])
            if isinstance(status, dict)
        }
        expected_total = len(expected_steps)
        if expected_total == 0:
            continue
        correct = 0
        for step_id, orientations in expected_steps.items():
            status = status_map.get(step_id)
            if not status or status.get("state") != "COMPLETED":
                continue
            observed_orientation = status.get("orientation")
            if _orientation_matches(observed_orientation, orientations):
                correct += 1
        stats = per_asset.setdefault(asset_id, {"sessions": 0, "correct": 0, "expected": 0})
        stats["sessions"] = stats.get("sessions", 0) + 1
        stats["correct"] = stats.get("correct", 0) + correct
        stats["expected"] = stats.get("expected", 0) + expected_total
        sessions += 1
        total_correct += correct
        total_expected += expected_total

    value = None
    if total_expected > 0:
        value = total_correct / total_expected

    asset_sections: Dict[str, Dict[str, object]] = {}
    for asset_id, stats in per_asset.items():
        expected = stats.get("expected", 0)
        accuracy = None
        if expected:
            accuracy = stats.get("correct", 0) / expected
        asset_sections[asset_id] = {
            "sessions": stats.get("sessions", 0),
            "accuracy": accuracy,
        }

    return AccuracyReport(
        value=value,
        threshold=threshold,
        sessions=sessions,
        correct=total_correct,
        expected=total_expected,
        assets=asset_sections,
        generated_ts=_now_iso(),
    )


def _build_asset_expectations(manifest: DemoManifest) -> Dict[str, Dict[str, set[str]]]:
    expectations: Dict[str, Dict[str, set[str]]] = {}
    for asset_id, asset in manifest.assets.items():
        step_map: Dict[str, set[str]] = {}
        for annotation in asset.annotations:
            step_map.setdefault(annotation.step_id.value, set()).add(annotation.orientation.value)
        expectations[asset_id] = step_map
    return expectations


def _orientation_matches(observed: object, expected_set: set[str]) -> bool:
    if not expected_set:
        return True
    normalized = str(observed) if isinstance(observed, str) else "NONE"
    if expected_set == {"NONE"}:
        return True
    if "NONE" in expected_set and normalized == "NONE":
        return True
    return normalized in expected_set


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
