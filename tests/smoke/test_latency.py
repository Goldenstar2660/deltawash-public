from __future__ import annotations

import pytest

from deltawash_pi.cli import smoke_camera


@pytest.mark.smoke
def test_mock_latency_benchmark_passes() -> None:
	code = smoke_camera.main([
		"--mock",
		"--frames",
		"5",
		"--latency-threshold-ms",
		"50",
	])
	assert code == 0


@pytest.mark.smoke
def test_mock_latency_benchmark_fails_when_threshold_too_low() -> None:
	code = smoke_camera.main([
		"--mock",
		"--frames",
		"5",
		"--latency-threshold-ms",
		"1",
	])
	assert code == 1
