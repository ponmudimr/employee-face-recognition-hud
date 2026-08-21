"""Unit tests for YuNet face detection logic in detect.py."""

import os
import sys
import numpy as np
import pytest

# Add src to path for pytest execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from detect import FaceDetector, DetectedFace


class TestDetectedFace:
    """Test suite for DetectedFace class container and tuple unpacking interface."""

    def test_initialization_and_properties(self) -> None:
        landmarks = np.array([[10, 10], [20, 10], [15, 15], [12, 20], [18, 20]], dtype=np.float32)
        raw_face = np.ones(15, dtype=np.float32)

        face = DetectedFace(
            x=10, y=20, w=50, h=60, score=0.95, landmarks=landmarks, raw_face=raw_face
        )

        assert face.x == 10
        assert face.y == 20
        assert face.w == 50
        assert face.h == 60
        assert face.score == 0.95
        assert face.bbox == (10, 20, 50, 60)
        assert face.landmarks.shape == (5, 2)
        assert face.raw_face.shape == (15,)

    def test_tuple_indexing(self) -> None:
        face = DetectedFace(x=15, y=25, w=35, h=45, score=0.88)
        assert face[0] == 15
        assert face[1] == 25
        assert face[2] == 35
        assert face[3] == 45
        assert face[4] == 0.88
        assert len(face) == 5

    def test_tuple_unpacking(self) -> None:
        face = DetectedFace(x=5, y=10, w=15, h=20, score=0.92)
        x, y, w, h, score = face
        assert (x, y, w, h, score) == (5, 10, 15, 20, 0.92)


class TestFaceDetector:
    """Test suite for FaceDetector initialization and execution flow."""

    def test_initialization(self) -> None:
        detector = FaceDetector(
            model_path="non_existent_model.onnx",
            confidence_threshold=0.7,
            target_size=(320, 240)
        )
        assert detector.model_path == "non_existent_model.onnx"
        assert detector.confidence_threshold == 0.7
        assert detector.target_size == (320, 240)

    def test_missing_model_file_graceful_handling(self) -> None:
        detector = FaceDetector(model_path="non_existent_model.onnx")
        success = detector.load_model()
        assert success is False

    def test_detect_empty_image(self) -> None:
        detector = FaceDetector(model_path="non_existent_model.onnx")
        faces = detector.detect(None)
        assert faces == []

        empty_img = np.array([], dtype=np.uint8)
        faces = detector.detect(empty_img)
        assert faces == []

    def test_detect_with_missing_model_returns_empty_list(self) -> None:
        detector = FaceDetector(model_path="non_existent_model.onnx")
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        faces = detector.detect(dummy_frame)
        assert isinstance(faces, list)
        assert len(faces) == 0
