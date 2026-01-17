from __future__ import annotations

from deltawash_pi.cli import roi_calibrate
from deltawash_pi.config.loader import ROI, load_config

from tests.unit.test_config_loader import _base_config_dict, _write_config


def test_roi_adjuster_respects_bounds() -> None:
    roi = ROI(x=350, y=330, width=80, height=90)
    adjuster = roi_calibrate.ROIAdjuster(roi, bounds=(400, 360))

    adjuster.apply(dx=200, dy=200, dw=200, dh=200)

    assert 0 <= adjuster.roi.x
    assert 0 <= adjuster.roi.y
    assert adjuster.roi.x + adjuster.roi.width <= 400
    assert adjuster.roi.y + adjuster.roi.height <= 360
    assert adjuster.roi.width >= adjuster.min_size
    assert adjuster.roi.height >= adjuster.min_size


def test_headless_cli_updates_config(tmp_path) -> None:
    data = _base_config_dict()
    config_path = _write_config(tmp_path, data)

    exit_code = roi_calibrate.main(
        [
            "--config",
            str(config_path),
            "--headless",
            "--dx",
            "15",
            "--dy",
            "-10",
            "--dw",
            "25",
            "--dh",
            "10",
            "--write-back",
        ]
    )

    assert exit_code == 0
    cfg = load_config(config_path)
    assert cfg.roi.x == data["roi"]["x"] + 15
    assert cfg.roi.y == data["roi"]["y"] - 10
    assert cfg.roi.width == data["roi"]["width"] + 25
    assert cfg.roi.height == data["roi"]["height"] + 10
