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

from machine_telemetry import MachineTelemetryClient, RUNNING_STATE_VALUES


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
