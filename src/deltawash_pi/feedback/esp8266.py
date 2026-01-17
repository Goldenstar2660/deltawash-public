"""HTTP LED client for ESP8266 step indicators."""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

import requests

from deltawash_pi.config.loader import Esp8266Config
from deltawash_pi.interpreter.types import LedSignalState, StepID

LOGGER = logging.getLogger(__name__)

_STEP_TO_NUMBER = {
    StepID.STEP_2: 2,
    StepID.STEP_3: 3,
    StepID.STEP_4: 4,
    StepID.STEP_5: 5,
    StepID.STEP_6: 6,
    StepID.STEP_7: 7,
}


class Esp8266Client:
    """Publishes LED state updates to an ESP8266 over HTTP."""

    def __init__(self, config: Esp8266Config, *, session: Optional[requests.Session] = None) -> None:
        self._config = config
        base_url = _normalize_host(config.host, config.endpoint) or "http://esp8266.local"
        self._signal_endpoint = f"{base_url.rstrip('/')}/signal"
        self._reset_endpoint = f"{base_url.rstrip('/')}/reset"
        self._timeout_s = max(config.timeout_ms, 1) / 1000.0
        self._session = session or requests.Session()
        self._session_id: Optional[str] = None
        self._disabled = not config.enabled
        self._last_error: Optional[str] = None
        self._last_states: Dict[StepID, LedSignalState] = {}

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def disabled(self) -> bool:
        return self._disabled

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def start_session(self, session_id: str) -> None:
        if not self._config.enabled:
            return
        self._reset_leds()
        self._session_id = session_id
        self._disabled = False
        self._last_error = None
        self._last_states.clear()

    def end_session(self) -> None:
        self._session_id = None
        self._last_error = None
        self._last_states.clear()

    def publish(self, step_id: StepID, state: LedSignalState, timestamp_ms: int) -> bool:
        if not self._config.enabled or self._disabled or not self._session_id:
            return False
        if self._last_states.get(step_id) is state:
            LOGGER.debug(
                "Skipping duplicate LED signal step=%s state=%s",
                step_id.value,
                state.value,
            )
            return True
        payload = self._build_payload(step_id, state, timestamp_ms)
        try:
            start = time.perf_counter()
            response = self._session.post(self._signal_endpoint, json=payload, timeout=self._timeout_s)
            latency_ms = (time.perf_counter() - start) * 1000.0
            response.raise_for_status()
            self._last_states[step_id] = state
            LOGGER.debug(
                "ESP8266 LED delivered step=%s state=%s latency=%.2fms",
                payload["step"],
                state.value,
                latency_ms,
            )
            return True
        except requests.RequestException as exc:
            self._disable(f"{exc.__class__.__name__}: {exc}")
            return False

    def _build_payload(self, step_id: StepID, state: LedSignalState, timestamp_ms: int) -> dict[str, object]:
        number = _STEP_TO_NUMBER.get(step_id)
        if number is None:
            raise ValueError(f"Unsupported step for LED payload: {step_id}")
        return {
            "step": number,
            "step_id": step_id.value,
            "state": state.value,
            "timestamp_ms": timestamp_ms,
            "blink_hz": self._config.blink_hz,
        }

    def _disable(self, reason: str) -> None:
        if self._disabled:
            return
        self._disabled = True
        self._last_error = reason
        LOGGER.warning(
            "Disabling ESP8266 LEDs for session %s (%s)",
            self._session_id or "<none>",
            reason,
        )

    def _reset_leds(self) -> None:
        try:
            response = self._session.post(self._reset_endpoint, timeout=self._timeout_s)
            response.raise_for_status()
            LOGGER.debug("ESP8266 LED reset OK")
        except requests.RequestException as exc:
            LOGGER.warning("ESP8266 LED reset failed: %s", exc)


def _normalize_host(host: Optional[str], endpoint: Optional[str]) -> Optional[str]:
    if isinstance(host, str) and host.strip():
        return host.strip()
    if not endpoint:
        return None
    endpoint = endpoint.strip()
    if not endpoint:
        return None
    if endpoint.endswith("/signal"):
        return endpoint[: -len("/signal")]
    return endpoint


__all__ = ["Esp8266Client"]
