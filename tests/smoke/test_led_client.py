from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from deltawash_pi.config.loader import Esp8266Config
from deltawash_pi.feedback.esp8266 import Esp8266Client
from deltawash_pi.interpreter.types import LedSignalState, StepID


class _LedHandler(BaseHTTPRequestHandler):
    delay: float = 0.0
    events: list[dict[str, object]] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if self.delay:
            time.sleep(self.delay)
        type(self).events.append(payload)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


@contextmanager
def _run_server(handler_cls: type[_LedHandler]):
    handler_cls.events = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=1)


def _client_for(endpoint: str, timeout_ms: int = 500) -> Esp8266Client:
    config = Esp8266Config(enabled=True, endpoint=endpoint, timeout_ms=timeout_ms, blink_hz=1.0)
    return Esp8266Client(config)


def test_led_client_success_and_unreachable_cases() -> None:
    class Handler(_LedHandler):
        delay = 0.0

    with _run_server(Handler) as server:
        endpoint = f"http://127.0.0.1:{server.server_address[1]}/signal"
        client = _client_for(endpoint)
        client.start_session("session-success")
        delivered = client.publish(StepID.STEP_3, LedSignalState.CURRENT, 123456)
        client.end_session()

    assert delivered
    assert Handler.events, "ESP handler should record at least one event"
    payload = Handler.events[-1]
    assert payload["step"] == 3
    assert payload["state"] == "CURRENT"

    # Unreachable endpoint should disable client without raising.
    client = _client_for("http://127.0.0.1:9/signal", timeout_ms=200)
    client.start_session("session-failure")
    delivered = client.publish(StepID.STEP_4, LedSignalState.CURRENT, 654321)
    assert delivered is False
    assert client.disabled


def test_led_client_latency_within_budget() -> None:
    class FastHandler(_LedHandler):
        delay = 0.05  # 50 ms simulated work

    with _run_server(FastHandler) as server:
        endpoint = f"http://127.0.0.1:{server.server_address[1]}/signal"
        client = _client_for(endpoint)
        client.start_session("latency-session")
        start = time.perf_counter()
        delivered = client.publish(StepID.STEP_5, LedSignalState.CURRENT, 111222)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        client.end_session()

    assert delivered
    assert elapsed_ms <= 500.0, "LED publish exceeded 500 ms latency budget"
