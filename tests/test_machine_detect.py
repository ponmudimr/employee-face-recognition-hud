"""Unit tests for ArUco marker detection and machine database matching in machine_detect.py."""

import json
import os
import sys
import tempfile
import cv2
import numpy as np
import pytest

# Add src to path for pytest execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from machine_detect import (
    MachineDetector,
    DetectedMarker,
    load_machine_database,
    match_machine,
    DEFAULT_ARUCO_DICT
)


def _make_marker_frame(marker_id: int, size: int = 640) -> np.ndarray:
    """Render an ArUco marker into a blank BGR frame for detector tests."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(DEFAULT_ARUCO_DICT)
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, 200)
    frame = np.full((size, size, 3), 255, dtype=np.uint8)
    frame[100:300, 100:300] = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)
    return frame


class TestDetectedMarker:
    """Test suite for DetectedMarker bbox computation."""

    def test_bbox_from_corners(self) -> None:
        corners = np.array([[10, 20], [110, 20], [110, 120], [10, 120]], dtype=np.float32)
        marker = DetectedMarker(marker_id=3, corners=corners)
        assert marker.bbox == (10, 20, 100, 100)

    def test_marker_id_cast_to_int(self) -> None:
        marker = DetectedMarker(marker_id=np.int32(5), corners=np.zeros((4, 2)))
        assert marker.marker_id == 5
        assert isinstance(marker.marker_id, int)


class TestMachineDetector:
    """Test suite for ArUco marker detection on rendered frames."""

    def test_detect_single_marker(self) -> None:
        frame = _make_marker_frame(marker_id=7)
        detector = MachineDetector()
        markers = detector.detect(frame)
        assert len(markers) == 1
        assert markers[0].marker_id == 7

    def test_detect_no_marker(self) -> None:
        frame = np.full((480, 640, 3), 255, dtype=np.uint8)
        detector = MachineDetector()
        markers = detector.detect(frame)
        assert markers == []

    def test_detect_none_frame(self) -> None:
        detector = MachineDetector()
        assert detector.detect(None) == []

    def test_detect_empty_frame(self) -> None:
        detector = MachineDetector()
        assert detector.detect(np.array([])) == []


class TestLoadMachineDatabase:
    """Test suite for loading the machinery JSON database."""

    def test_load_missing_file(self) -> None:
        db = load_machine_database("/nonexistent/path/machines.json")
        assert db == []

    def test_load_valid_database(self) -> None:
        records = [{"marker_id": 1, "name": "Filler", "api_base_url": "http://host:3001"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(records, f)
            path = f.name
        try:
            db = load_machine_database(path)
            assert db == records
        finally:
            os.remove(path)

    def test_load_invalid_format(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"not": "a list"}, f)
            path = f.name
        try:
            db = load_machine_database(path)
            assert db == []
        finally:
            os.remove(path)


class TestMatchMachine:
    """Test suite for marker-ID-to-machine lookup logic."""

    def test_match_found(self) -> None:
        db = [
            {"marker_id": 1, "name": "Filler", "api_base_url": "http://host:3001"},
            {"marker_id": 2, "name": "Capper", "api_base_url": "http://host:3002"},
        ]
        rec = match_machine(2, db)
        assert rec is not None
        assert rec["name"] == "Capper"

    def test_match_not_found(self) -> None:
        db = [{"marker_id": 1, "name": "Filler", "api_base_url": "http://host:3001"}]
        assert match_machine(99, db) is None

    def test_match_empty_database(self) -> None:
        assert match_machine(1, []) is None
