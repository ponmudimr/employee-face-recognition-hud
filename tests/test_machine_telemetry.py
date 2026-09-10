"""Unit tests for the background machine telemetry polling client in machine_telemetry.py."""

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from machine_telemetry import MachineTelemetryClient


class _StateHandler(BaseHTTPRequestHandler):
    """Minimal HTTP server standing in for a BottleWise-style backend's /api/state endpoint."""

    state_payload = {"phase": "Filling", "completedCount": 42}

    def do_GET(self) -> None:
        if self.path == "/api/state":
            body = json.dumps(self.state_payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args) -> None:
        pass  # silence request logging in test output


@pytest.fixture
def mock_backend():
    """Spin up a local HTTP server on an ephemeral port serving /api/state."""
    server = HTTPServer(("127.0.0.1", 0), _StateHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


class TestMachineTelemetryClient:
    """Test suite for the background telemetry polling client."""

    def test_initial_state_before_first_poll(self) -> None:
        client = MachineTelemetryClient("http://127.0.0.1:1", poll_interval=1.0)
        assert client.get_latest_state() is None
        assert client.is_connected() is False

    def test_successful_poll_updates_state(self, mock_backend) -> None:
        client = MachineTelemetryClient(mock_backend, poll_interval=0.1, timeout=1.0)
        client.start()
        try:
            deadline = time.time() + 2.0
            while time.time() < deadline and not client.is_connected():
                time.sleep(0.05)
            assert client.is_connected() is True
            state = client.get_latest_state()
            assert state == {"phase": "Filling", "completedCount": 42}
        finally:
            client.stop()

    def test_unreachable_backend_stays_disconnected(self) -> None:
        client = MachineTelemetryClient("http://127.0.0.1:1", poll_interval=0.1, timeout=0.2)
        client.start()
        try:
            time.sleep(0.5)
            assert client.is_connected() is False
            assert client.get_latest_state() is None
        finally:
            client.stop()

    def test_trailing_slash_stripped_from_base_url(self) -> None:
        client = MachineTelemetryClient("http://example.com/")
        assert client.api_base_url == "http://example.com"

    def test_start_is_idempotent(self, mock_backend) -> None:
        client = MachineTelemetryClient(mock_backend, poll_interval=0.1, timeout=1.0)
        client.start()
        first_thread = client._thread
        client.start()  # should be a no-op, not spawn a second thread
        assert client._thread is first_thread
        client.stop()
