"""Background polling client for a machine's live telemetry, fetched from its BottleWise-style
backend REST API (GET /api/state). Runs on its own daemon thread so a slow/unreachable backend
never blocks the HUD's detection or render loop -- the same async philosophy main.py already
uses for face detection/recognition.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_S = 1.0
DEFAULT_TIMEOUT_S = 2.0


class MachineTelemetryClient:
    """Polls a single machine's `GET {api_base_url}/api/state` endpoint on a background thread."""

    def __init__(
        self,
        api_base_url: str,
        poll_interval: float = DEFAULT_POLL_INTERVAL_S,
        timeout: float = DEFAULT_TIMEOUT_S
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.timeout = timeout

        self._lock = threading.Lock()
        self._latest_state: Optional[Dict[str, Any]] = None
        self._connected = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background polling thread (no-op if already running)."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info(f"Started telemetry polling for '{self.api_base_url}'.")

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.timeout + 1.0)

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                resp = requests.get(f"{self.api_base_url}/api/state", timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                with self._lock:
                    self._latest_state = data
                    self._connected = True
            except Exception as e:
                logger.debug(f"Telemetry poll failed for '{self.api_base_url}': {e}")
                with self._lock:
                    self._connected = False
            self._stop_event.wait(self.poll_interval)

    def get_latest_state(self) -> Optional[Dict[str, Any]]:
        """Return the most recently polled state snapshot, or None if never successfully polled."""
        with self._lock:
            return dict(self._latest_state) if self._latest_state is not None else None

    def is_connected(self) -> bool:
        """Whether the most recent poll succeeded."""
        with self._lock:
            return self._connected
