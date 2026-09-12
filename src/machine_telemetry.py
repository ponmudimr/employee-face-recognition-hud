"""Background MQTT subscriber that tracks a machine's live running/stopped state and
locally accumulates running/downtime hours from it.

This talks directly to the MQTT broker (e.g. the public broker.hivemq.com the machine's
PLC/sensor nodes already publish to) -- no Node.js backend involved. Only the start/stop
state is real sensor data; running_hours/stopped_hours are derived locally by timing how
long the machine has spent in each state, persisted to a small local JSON file so the
totals survive a pipeline restart. Everything else shown on the HUD card (production %,
parts life, maintenance schedule) is static placeholder data stored per-machine in
machines.json, not something this client is responsible for.
"""

import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, Optional, Tuple
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# Payload values (case-insensitive) treated as "machine is running". Anything else on
# the status topic is treated as stopped.
RUNNING_STATE_VALUES = {"RUNNING", "RUN", "ON", "1", "TRUE", "START", "STARTED"}

# No message on the status topic within this window -> treat as disconnected, even if
# the underlying MQTT socket is technically still open (broker/publisher could be idle).
STALE_AFTER_S = 30.0

# Candidate field names (checked case-insensitively) to look for the running/stopped
# indicator inside a JSON payload, in priority order.
STATUS_FIELD_NAMES = ("status", "state", "run_state", "running", "machine_status")

# Candidate field names (checked case-insensitively) to look for a bottle/parts
# produced count inside a JSON payload, in priority order.
COUNT_FIELD_NAMES = ("bottle_count", "bottles_filled", "bottles", "count", "parts_produced", "produced")


def _extract_status_value(raw: str) -> str:
    """Pull the running/stopped indicator out of a raw MQTT payload.

    The exact payload format for a given status topic isn't always known in advance --
    some publish a bare string ("RUNNING"), others bundle multiple fields into one JSON
    message (the "data" in a topic like "aries/bottlefeeder/data" suggests this). If the
    payload parses as a JSON object, look for a plausible status field inside it (any of
    STATUS_FIELD_NAMES, case-insensitive) and use *that* value instead of the raw
    payload -- otherwise a bundled JSON message would never match a plain RUNNING/STOPPED
    string comparison and the machine would silently appear permanently STOPPED.

    Args:
        raw: Decoded MQTT payload string.

    Returns:
        The string to compare against `RUNNING_STATE_VALUES` (uppercased comparison
        happens in `_apply_status_message`).
    """
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return raw

    if not isinstance(parsed, dict):
        return raw

    lower_map = {str(k).lower(): v for k, v in parsed.items()}
    for field in STATUS_FIELD_NAMES:
        if field in lower_map:
            return str(lower_map[field])

    logger.warning(
        f"JSON payload has no recognizable status field (checked {STATUS_FIELD_NAMES}): {raw!r}"
    )
    return raw


def _extract_status_and_count(raw: str) -> Tuple[str, Optional[float]]:
    """Pull both the running/stopped indicator and a bottle/parts-produced count out
    of a raw MQTT payload.

    The real "aries/bottlefeeder/data" topic sends a plain delimited payload rather
    than JSON: the first number is the on/off state (1/0) and the last number is the
    running total of bottles filled (e.g. "1,4820" or "1 4820"). A JSON payload is
    also supported defensively (see `_extract_status_value`), checking
    `COUNT_FIELD_NAMES` for the count in that case.

    Args:
        raw: Decoded MQTT payload string.

    Returns:
        `(status_value, bottle_count)` -- `status_value` is what `_apply_status_message`
        compares against `RUNNING_STATE_VALUES`; `bottle_count` is `None` if no count
        could be determined from this payload.
    """
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        parsed = None

    if isinstance(parsed, dict):
        status = _extract_status_value(raw)
        count: Optional[float] = None
        lower_map = {str(k).lower(): v for k, v in parsed.items()}
        for field in COUNT_FIELD_NAMES:
            if field in lower_map:
                try:
                    count = float(lower_map[field])
                except (TypeError, ValueError):
                    pass
                break
        return status, count

    # Plain payload, e.g. "1,4820" or "1 4820" -- not JSON.
    numbers = re.findall(r"-?\d+\.?\d*", raw)
    if len(numbers) >= 2:
        try:
            return numbers[0], float(numbers[-1])
        except ValueError:
            return numbers[0], None
    if len(numbers) == 1:
        return numbers[0], None
    return raw, None


class MachineTelemetryClient:
    """Subscribes to one machine's MQTT start/stop topic and accumulates run/down hours."""

    def __init__(
        self,
        machine_key: str,
        broker: str = "broker.hivemq.com",
        port: int = 1883,
        status_topic: str = "bottlewise/conveyor/input/state",
        hours_state_dir: str = "machinery/database"
    ) -> None:
        """
        Args:
            machine_key: Stable identifier for this machine (e.g. its marker ID), used
                to name the local hours-persistence file.
            broker: MQTT broker hostname.
            port: MQTT broker port (1883 for plain TCP).
            status_topic: Topic whose payload indicates running/stopped state.
            hours_state_dir: Directory to persist accumulated hours into.
        """
        self.machine_key = str(machine_key)
        self.broker = broker
        self.port = port
        self.status_topic = status_topic
        self.hours_state_path = os.path.join(hours_state_dir, f"hours_{self.machine_key}.json")

        self._lock = threading.Lock()
        self._status: Optional[str] = None
        self._status_since: Optional[float] = None
        self._running_hours_base = 0.0
        self._stopped_hours_base = 0.0
        self._last_message_time: Optional[float] = None
        self._bottle_count: Optional[float] = None

        self._load_persisted_hours()

        self._client = self._build_client()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _build_client(self) -> Any:
        client_id = f"hud-{self.machine_key}-{os.getpid()}"
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        except AttributeError:
            # Older paho-mqtt (1.x) has no CallbackAPIVersion -- falls back to its
            # default client, whose on_message signature is unchanged from v2.
            client = mqtt.Client(client_id=client_id)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        return client

    def _load_persisted_hours(self) -> None:
        if not os.path.exists(self.hours_state_path):
            return
        try:
            with open(self.hours_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._running_hours_base = float(data.get("running_hours", 0.0))
                self._stopped_hours_base = float(data.get("stopped_hours", 0.0))
        except Exception as e:
            logger.warning(f"Could not load persisted hours for '{self.machine_key}': {e}")

    def _save_persisted_hours(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.hours_state_path), exist_ok=True)
            with open(self.hours_state_path, "w", encoding="utf-8") as f:
                json.dump({
                    "running_hours": self._running_hours_base,
                    "stopped_hours": self._stopped_hours_base
                }, f)
        except Exception as e:
            logger.debug(f"Could not persist hours for '{self.machine_key}': {e}")

    def start(self) -> None:
        """Start the background MQTT connection thread (no-op if already running)."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(
            f"Started MQTT telemetry for '{self.machine_key}' via "
            f"{self.broker}:{self.port}, topic '{self.status_topic}'."
        )

    def _run(self) -> None:
        try:
            self._client.connect(self.broker, self.port, keepalive=30)
        except Exception as e:
            logger.warning(f"MQTT connect failed for '{self.machine_key}': {e}")
            return
        self._client.loop_start()
        self._stop_event.wait()
        self._client.loop_stop()
        try:
            self._client.disconnect()
        except Exception:
            pass

    def _on_connect(self, client: Any, userdata: Any, flags: Any, *args: Any) -> None:
        logger.info(f"MQTT connected for '{self.machine_key}', subscribing to '{self.status_topic}'.")
        client.subscribe(self.status_topic, qos=0)

    def _on_disconnect(self, client: Any, userdata: Any, *args: Any) -> None:
        logger.debug(f"MQTT disconnected for '{self.machine_key}'.")

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        try:
            value = msg.payload.decode("utf-8", errors="replace").strip()
        except Exception:
            return
        status_value, bottle_count = _extract_status_and_count(value)
        self._apply_status_message(status_value, time.time(), bottle_count=bottle_count)

    def _apply_status_message(self, value: str, now: float, bottle_count: Optional[float] = None) -> None:
        """Update running/stopped state (and, if provided, the latest bottle count)
        from a decoded status-topic payload. Split out from `_on_message` so it's
        directly unit-testable without a real MQTT message."""
        new_status = "RUNNING" if value.upper() in RUNNING_STATE_VALUES else "STOPPED"

        with self._lock:
            self._last_message_time = now
            if bottle_count is not None:
                self._bottle_count = bottle_count
            if self._status is None:
                # First message ever seen: start the clock, don't backdate any hours.
                self._status = new_status
                self._status_since = now
                return

            if new_status != self._status:
                elapsed_h = (now - self._status_since) / 3600.0
                if self._status == "RUNNING":
                    self._running_hours_base += elapsed_h
                else:
                    self._stopped_hours_base += elapsed_h
                self._save_persisted_hours()
                self._status = new_status
                self._status_since = now

    def get_latest_state(self, now: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Return current status plus live-accumulated running/stopped hours (computed
        up to the moment of this call), or None if no status message has ever arrived.

        Args:
            now: Override for the current time (epoch seconds). Defaults to `time.time()`;
                exposed only so tests can drive a consistent simulated clock.
        """
        with self._lock:
            if self._status is None:
                return None
            if now is None:
                now = time.time()
            elapsed_h = (now - self._status_since) / 3600.0
            running_hours = self._running_hours_base + (elapsed_h if self._status == "RUNNING" else 0.0)
            stopped_hours = self._stopped_hours_base + (elapsed_h if self._status == "STOPPED" else 0.0)
            return {
                "status": self._status,
                "running_hours": running_hours,
                "stopped_hours": stopped_hours,
                "bottles_filled": self._bottle_count if self._bottle_count is not None else 0.0,
            }

    def is_connected(self) -> bool:
        """Whether a status message has arrived recently (not just whether the MQTT
        socket is open -- the broker could be up with nothing actually publishing)."""
        with self._lock:
            if self._last_message_time is None:
                return False
            return (time.time() - self._last_message_time) < STALE_AFTER_S

    def stop(self) -> None:
        """Stop the background MQTT thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
