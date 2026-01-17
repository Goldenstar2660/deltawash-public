"""Shared utilities for CLI entrypoints."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Optional

from deltawash_pi.config.loader import Config, ConfigError, load_config

DEFAULT_CONFIG_PATH = "config/example.yaml"
LOCAL_CONFIG_PATH = "config/local.yaml"


def add_common_args(parser: argparse.ArgumentParser, *, require_config: bool = False) -> None:
    default = None if require_config else None
    parser.add_argument(
        "--config",
        dest="config",
        default=default,
        required=require_config,
        help=(
            "Path to YAML config file (default: "
            f"{LOCAL_CONFIG_PATH} if present, else {DEFAULT_CONFIG_PATH})"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging for troubleshooting",
    )


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")
    if verbose:
        return
    # Quiet noisy native/ML backends unless explicitly requested.
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("GLOG_minloglevel", "2")
    for name in (
        "absl",
        "libcamera",
        "picamera2",
        "tensorflow",
        "tflite_runtime",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


def load_cli_config(config_path: Optional[str]) -> Config:
    if config_path:
        resolved = config_path
    else:
        local = Path(LOCAL_CONFIG_PATH)
        resolved = str(local) if local.exists() else DEFAULT_CONFIG_PATH
    try:
        return load_config(resolved)
    except ConfigError as exc:
        raise SystemExit(f"Config validation failed: {exc}") from exc
