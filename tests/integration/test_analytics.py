from __future__ import annotations

import json
from pathlib import Path

import pytest

from deltawash_pi.cli.analytics import _compute_accuracy_report
from deltawash_pi.demo.replay import load_manifest
from deltawash_pi.logging.aggregates import load_session_records, summarize_records


def _write_log(path: Path, records: list[dict]) -> None:
    lines = "\n".join(json.dumps(record) for record in records)
    path.write_text(lines + "\n", encoding="utf-8")


def test_summarize_records_aggregates_expected_metrics(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    record_a = {
        "session_id": "session-a",
        "config_version": "cfg-1",
        "model_version": "abc123",
        "start_ts": "2026-01-10T00:00:00Z",
        "end_ts": "2026-01-10T00:00:10Z",
        "roi_rect": {"x": 0, "y": 0, "width": 400, "height": 300},
        "demo_mode": False,
        "demo_asset_id": None,
        "step_statuses": [
            {
                "step_id": "STEP_2",
                "state": "COMPLETED",
                "orientation": "NONE",
                "accumulated_ms": 3000,
                "completed_ts": "2026-01-10T00:00:05Z",
                "uncertainty_count": 0,
            },
            {
                "step_id": "STEP_3",
                "state": "IN_PROGRESS",
                "orientation": "RIGHT_OVER_LEFT",
                "accumulated_ms": 1200,
                "completed_ts": None,
                "uncertainty_count": 1,
            },
        ],
        "uncertainty_events": [
            {"timestamp_ms": 1200, "reason": "LOW_CONFIDENCE"},
        ],
        "fallback_events": [
            {"timestamp_ms": 1500, "reason": "MODEL_LOW_CONFIDENCE"},
        ],
        "total_rubbing_ms": 4200,
        "model_inference_count": 10,
        "heuristic_fallback_count": 2,
        "avg_inference_time_ms": 5.0,
        "inference_time_samples": 2,
        "inference_time_sum_ms": 10.0,
        "avg_model_confidence": 0.8,
        "model_confidence_samples": 10,
        "model_confidence_sum": 8.0,
        "model_usage_rate": 0.83,
        "notes": [],
    }

    record_b = {
        "session_id": "session-b",
        "config_version": "cfg-1",
        "model_version": "abc123",
        "start_ts": "2026-01-10T00:00:00Z",
        "end_ts": "2026-01-10T00:00:08Z",
        "roi_rect": {"x": 0, "y": 0, "width": 400, "height": 300},
        "demo_mode": False,
        "demo_asset_id": None,
        "step_statuses": [
            {
                "step_id": "STEP_2",
                "state": "COMPLETED",
                "orientation": "NONE",
                "accumulated_ms": 3200,
                "completed_ts": "2026-01-10T00:00:05Z",
                "uncertainty_count": 0,
            },
            {
                "step_id": "STEP_3",
                "state": "COMPLETED",
                "orientation": "RIGHT_OVER_LEFT",
                "accumulated_ms": 3100,
                "completed_ts": "2026-01-10T00:00:07Z",
                "uncertainty_count": 0,
            },
        ],
        "uncertainty_events": [],
        "fallback_events": [
            {"timestamp_ms": 900, "reason": "WINDOW_INCOMPLETE"},
        ],
        "total_rubbing_ms": 6300,
        "model_inference_count": 5,
        "heuristic_fallback_count": 5,
        "avg_inference_time_ms": 8.0,
        "inference_time_samples": 3,
        "inference_time_sum_ms": 24.0,
        "avg_model_confidence": 0.9,
        "model_confidence_samples": 5,
        "model_confidence_sum": 4.5,
        "model_usage_rate": 0.5,
        "notes": [],
    }

    _write_log(log_dir / "2026-01-10.jsonl", [record_a])
    _write_log(log_dir / "2026-01-10.jsonl", [record_b])

    records = load_session_records(log_dir)
    summary = summarize_records(records)

    assert summary.sessions_count == 2
    assert summary.most_missed_step == "STEP_3"
    assert summary.average_step_times_ms["STEP_2"] == 3100.0
    assert summary.average_step_times_ms["STEP_3"] == 2150.0
    assert summary.uncertainty_frequency == {"LOW_CONFIDENCE": 1}
    assert summary.fallback_frequency == {
        "MODEL_LOW_CONFIDENCE": 1,
        "WINDOW_INCOMPLETE": 1,
    }
    assert summary.model_usage_rate == pytest.approx(15 / 22)
    assert summary.avg_model_confidence == pytest.approx((8.0 + 4.5) / 15)
    assert summary.avg_inference_time_ms == pytest.approx((10.0 + 24.0) / 5)


def test_accuracy_report_aggregates_demo_sessions(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    asset_file = tmp_path / "demo_a.npz"
    asset_file.write_bytes(b"demo")
    manifest_payload = {
        "version": "0.1",
        "generated": "2026-01-10",
        "assets": [
            {
                "id": "asset-a",
                "file": asset_file.name,
                "fps": 24.0,
                "total_frames": 200,
                "annotations": [
                    {
                        "step_id": "STEP_2",
                        "orientation": "NONE",
                        "start_ms": 0,
                        "end_ms": 3000,
                    },
                    {
                        "step_id": "STEP_3",
                        "orientation": "RIGHT_OVER_LEFT",
                        "start_ms": 3200,
                        "end_ms": 6200,
                    },
                ],
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

    manifest = load_manifest(manifest_path)

    session_good = {
        "demo_mode": True,
        "demo_asset_id": "asset-a",
        "step_statuses": [
            {"step_id": "STEP_2", "state": "COMPLETED", "orientation": "NONE"},
            {
                "step_id": "STEP_3",
                "state": "COMPLETED",
                "orientation": "RIGHT_OVER_LEFT",
            },
        ],
    }
    session_partial = {
        "demo_mode": True,
        "demo_asset_id": "asset-a",
        "step_statuses": [
            {"step_id": "STEP_2", "state": "COMPLETED", "orientation": "NONE"},
            {"step_id": "STEP_3", "state": "IN_PROGRESS", "orientation": "RIGHT_OVER_LEFT"},
        ],
    }

    records = [session_good, session_partial]
    report = _compute_accuracy_report(manifest, records, threshold=0.7)
    assert report.value == pytest.approx(0.75)
    assert report.sessions == 2
    assert report.passed is True

    failing_report = _compute_accuracy_report(manifest, records, threshold=0.9)
    assert failing_report.passed is False
