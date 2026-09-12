"""Unit tests for the MQTT-based machine status/hours tracking client in machine_telemetry.py.

Tests the state-accumulation logic directly (via `_apply_status_message`, the same method
`_on_message` calls after decoding a real MQTT payload) rather than requiring a live broker
connection -- keeps these fast, deterministic, and independent of network access.
"""

import json
import os
import sys
import tempfile
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from machine_telemetry import (
    MachineTelemetryClient,
    RUNNING_STATE_VALUES,
    _extract_status_value,
    _extract_status_and_count,
)


@pytest.fixture
def tmp_hours_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestMachineTelemetryClient:
    """Test suite for status tracking and running/stopped hour accumulation."""

    def test_initial_state_before_any_message(self, tmp_hours_dir) -> None:
        client = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        assert client.get_latest_state() is None
        assert client.is_connected() is False

    def test_first_message_sets_status_without_backdating_hours(self, tmp_hours_dir) -> None:
        client = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        client._apply_status_message("RUNNING", time.time())
        state = client.get_latest_state()
        assert state["status"] == "RUNNING"
        assert state["running_hours"] == pytest.approx(0.0, abs=1e-6)
        assert state["stopped_hours"] == pytest.approx(0.0, abs=1e-6)

    def test_hours_accumulate_across_a_status_change(self, tmp_hours_dir) -> None:
        client = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        t0 = time.time()
        client._apply_status_message("RUNNING", t0)
        # Simulate 2 hours of running before it stops.
        t1 = t0 + 2 * 3600
        client._apply_status_message("STOPPED", t1)
        state = client.get_latest_state(now=t1)  # no time elapsed since the STOPPED transition
        assert state["status"] == "STOPPED"
        assert state["running_hours"] == pytest.approx(2.0, abs=1e-3)
        assert state["stopped_hours"] == pytest.approx(0.0, abs=1e-3)

    def test_unrecognized_payload_treated_as_stopped(self, tmp_hours_dir) -> None:
        client = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        client._apply_status_message("garbage_value", time.time())
        assert client.get_latest_state()["status"] == "STOPPED"

    def test_running_state_values_case_insensitive(self, tmp_hours_dir) -> None:
        client = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        client._apply_status_message("running", time.time())
        assert client.get_latest_state()["status"] == "RUNNING"

    def test_repeated_same_status_does_not_double_count(self, tmp_hours_dir) -> None:
        client = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        t0 = time.time()
        client._apply_status_message("RUNNING", t0)
        client._apply_status_message("RUNNING", t0 + 3600)  # still running, no transition
        client._apply_status_message("STOPPED", t0 + 2 * 3600)
        state = client.get_latest_state()
        # Only one RUNNING->STOPPED transition occurred, spanning 2 hours total.
        assert state["running_hours"] == pytest.approx(2.0, abs=1e-3)

    def test_hours_persist_across_client_instances(self, tmp_hours_dir) -> None:
        client1 = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        t0 = time.time()
        client1._apply_status_message("RUNNING", t0)
        client1._apply_status_message("STOPPED", t0 + 3600)  # 1 hour running, persisted

        client2 = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        client2._apply_status_message("RUNNING", t0 + 3600)
        state = client2.get_latest_state(now=t0 + 3600)  # no time elapsed since re-starting
        assert state["running_hours"] == pytest.approx(1.0, abs=1e-3)

    def test_is_connected_reflects_recent_message(self, tmp_hours_dir) -> None:
        client = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        assert client.is_connected() is False
        client._apply_status_message("RUNNING", time.time())
        assert client.is_connected() is True

    def test_different_machine_keys_use_separate_hours_files(self, tmp_hours_dir) -> None:
        client_a = MachineTelemetryClient("machine_a", hours_state_dir=tmp_hours_dir)
        client_b = MachineTelemetryClient("machine_b", hours_state_dir=tmp_hours_dir)
        assert client_a.hours_state_path != client_b.hours_state_path

    def test_running_state_values_constant_is_reasonable(self) -> None:
        assert "RUNNING" in RUNNING_STATE_VALUES
        assert "STOPPED" not in RUNNING_STATE_VALUES


class TestExtractStatusValue:
    """Test suite for pulling a status indicator out of a raw MQTT payload -- covers the
    real risk that a topic bundling multiple fields into one JSON message (as the topic
    name "aries/bottlefeeder/data" suggests) would otherwise never match a plain
    RUNNING/STOPPED string comparison and silently look permanently STOPPED."""

    def test_plain_string_passed_through(self) -> None:
        assert _extract_status_value("RUNNING") == "RUNNING"
        assert _extract_status_value("STOPPED") == "STOPPED"

    def test_json_with_status_field(self) -> None:
        assert _extract_status_value('{"status": "RUNNING", "speed": 5.2}') == "RUNNING"

    def test_json_with_alternate_field_name(self) -> None:
        assert _extract_status_value('{"state": "STOPPED"}') == "STOPPED"
        assert _extract_status_value('{"run_state": "RUNNING"}') == "RUNNING"

    def test_json_field_name_case_insensitive(self) -> None:
        assert _extract_status_value('{"STATUS": "RUNNING"}') == "RUNNING"

    def test_json_boolean_field_value(self) -> None:
        # str(True) == "TRUE", which is in RUNNING_STATE_VALUES -- booleans work
        # naturally without special-casing.
        assert _extract_status_value('{"running": true}') == "True"

    def test_json_numeric_field_value(self) -> None:
        assert _extract_status_value('{"status": 1}') == "1"

    def test_json_with_no_recognizable_field_returns_raw(self) -> None:
        raw = '{"speed": 5.2, "temperature": 40}'
        assert _extract_status_value(raw) == raw

    def test_invalid_json_returns_raw_string(self) -> None:
        assert _extract_status_value("not json at all") == "not json at all"

    def test_json_array_returns_raw(self) -> None:
        raw = '["RUNNING", "extra"]'
        assert _extract_status_value(raw) == raw

    def test_end_to_end_json_payload_via_apply_status_message(self, tmp_hours_dir) -> None:
        """The actual bug this defends against: a bundled JSON payload must still be
        correctly recognized as RUNNING, not silently treated as STOPPED forever."""
        client = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        client._apply_status_message(_extract_status_value('{"status": "RUNNING", "speed": 5.2}'), time.time())
        assert client.get_latest_state()["status"] == "RUNNING"


class TestExtractStatusAndCount:
    """Test suite for the real 'aries/bottlefeeder/data' payload format: a plain
    delimited string where the first number is on/off state and the last number is
    the running total of bottles filled (e.g. "1,4820"), not JSON."""

    def test_comma_delimited_running_with_count(self) -> None:
        assert _extract_status_and_count("1,4820") == ("1", 4820.0)

    def test_space_delimited_stopped_with_count(self) -> None:
        assert _extract_status_and_count("0 4820") == ("0", 4820.0)

    def test_single_number_only_no_count(self) -> None:
        assert _extract_status_and_count("1") == ("1", None)

    def test_plain_string_status_no_numbers(self) -> None:
        assert _extract_status_and_count("RUNNING") == ("RUNNING", None)

    def test_json_payload_with_count_field(self) -> None:
        status, count = _extract_status_and_count('{"status": "RUNNING", "bottle_count": 4820}')
        assert status == "RUNNING"
        assert count == 4820.0

    def test_json_payload_without_count_field(self) -> None:
        status, count = _extract_status_and_count('{"status": "RUNNING"}')
        assert status == "RUNNING"
        assert count is None

    def test_end_to_end_bottle_count_reaches_latest_state(self, tmp_hours_dir) -> None:
        client = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        status, count = _extract_status_and_count("1,4820")
        client._apply_status_message(status, time.time(), bottle_count=count)
        state = client.get_latest_state()
        assert state["status"] == "RUNNING"
        assert state["bottles_filled"] == 4820.0

    def test_bottle_count_persists_after_status_change_without_new_count(self, tmp_hours_dir) -> None:
        """A later message with no parseable count shouldn't wipe out the last known count."""
        client = MachineTelemetryClient("m1", hours_state_dir=tmp_hours_dir)
        client._apply_status_message("RUNNING", time.time(), bottle_count=4820.0)
        client._apply_status_message("STOPPED", time.time() + 10, bottle_count=None)
        assert client.get_latest_state()["bottles_filled"] == 4820.0
