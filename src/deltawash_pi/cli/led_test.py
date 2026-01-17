"""ESP8266 LED signaling smoke test utility."""

from __future__ import annotations

import argparse
import logging
import time
from typing import Sequence

from deltawash_pi.cli._helpers import add_common_args, configure_logging, load_cli_config
from deltawash_pi.feedback.esp8266 import Esp8266Client
from deltawash_pi.interpreter.types import LedSignalState, StepID

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deltawash-led-test",
        description="Send ad-hoc LED payloads to the configured ESP8266 endpoint.",
    )
    add_common_args(parser)
    parser.add_argument(
        "--step",
        required=True,
        choices=[step.value for step in StepID],
        help="Canonical WHO step ID to target",
    )
    parser.add_argument(
        "--state",
        default=LedSignalState.CURRENT.value,
        choices=[state.value for state in LedSignalState],
        help="LED state payload to emit",
    )
    parser.add_argument(
        "--message",
        help="Optional note to include in diagnostic output",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.verbose)
    config = load_cli_config(args.config)
    LOGGER.info("Config loaded (version=%s)", config.config_version)

    if not config.esp8266.enabled:
        LOGGER.error("ESP8266 block is disabled in %s; enable esp8266.enabled to run tests", config.source)
        return 2

    client = Esp8266Client(config.esp8266)
    client.start_session("led-test")
    step = StepID(args.step)
    state = LedSignalState(args.state)
    timestamp_ms = int(time.time() * 1000)

    endpoint = config.esp8266.host or config.esp8266.endpoint
    LOGGER.info("Sending step=%s state=%s to %s", step.value, state.value, endpoint)
    delivered = client.publish(step, state, timestamp_ms)
    client.end_session()

    if not delivered:
        LOGGER.error("LED publish failed; inspect logs for disable reason")
        return 1

    if args.message:
        LOGGER.info("Message: %s", args.message)
    LOGGER.info("LED publish succeeded")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
