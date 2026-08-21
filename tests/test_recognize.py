"""Unit tests for embedding cosine similarity and SFace matching logic in recognize.py."""

import json
import os
import sys
import tempfile
import numpy as np
import pytest

# Add src to path for pytest execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from recognize import (
    cosine_similarity,
    match_face,
    load_database,
    FaceRecognizer,
    DEFAULT_MATCH_THRESHOLD
)


class TestCosineSimilarity:
    """Test suite for cosine similarity calculation between embedding vectors."""

    def test_identical_vectors(self) -> None:
        v1 = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
        v2 = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
        sim = cosine_similarity(v1, v2)
        assert pytest.approx(sim, abs=1e-5) == 1.0

    def test_orthogonal_vectors(self) -> None:
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        sim = cosine_similarity(v1, v2)
        assert pytest.approx(sim, abs=1e-5) == 0.0

    def test_opposite_vectors(self) -> None:
        v1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        v2 = np.array([-1.0, -2.0, -3.0], dtype=np.float32)
        sim = cosine_similarity(v1, v2)
        assert pytest.approx(sim, abs=1e-5) == -1.0

    def test_zero_vector(self) -> None:
        v1 = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        sim = cosine_similarity(v1, v2)
        assert sim == 0.0


class TestMatchFace:
    """Test suite for matching target face embeddings against database records."""

    @pytest.fixture
    def sample_database(self) -> list:
        return [
            {
                "id": "EMP-001",
                "name": "Alice Smith",
                "role": "Engineer",
                "embedding": [1.0, 0.0, 0.0, 0.0]
            },
            {
                "id": "EMP-002",
                "name": "Bob Jones",
                "role": "Technician",
                "embedding": [0.0, 1.0, 0.0, 0.0]
            }
        ]

    def test_exact_match(self, sample_database: list) -> None:
        query_emb = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        match = match_face(query_emb, sample_database, threshold=DEFAULT_MATCH_THRESHOLD)

        assert match is not None
        assert match["id"] == "EMP-001"
        assert match["name"] == "Alice Smith"
        assert pytest.approx(match["similarity"], abs=1e-4) == 1.0

    def test_match_below_threshold(self, sample_database: list) -> None:
        # Vector with low similarity (< 0.363) to both EMP-001 and EMP-002
        query_emb = np.array([0.1, 0.1, 0.98, 0.0], dtype=np.float32)
        match = match_face(query_emb, sample_database, threshold=DEFAULT_MATCH_THRESHOLD)
        assert match is None

    def test_empty_database(self) -> None:
        query_emb = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        match = match_face(query_emb, [], threshold=DEFAULT_MATCH_THRESHOLD)
        assert match is None

    def test_none_embedding(self, sample_database: list) -> None:
        match = match_face(None, sample_database, threshold=DEFAULT_MATCH_THRESHOLD)
        assert match is None

    def test_zero_embedding(self, sample_database: list) -> None:
        query_emb = np.zeros(128, dtype=np.float32)
        match = match_face(query_emb, sample_database, threshold=DEFAULT_MATCH_THRESHOLD)
        assert match is None


class TestFaceRecognizer:
    """Test suite for FaceRecognizer class functionality."""

    def test_default_threshold(self) -> None:
        recognizer = FaceRecognizer(model_path="non_existent.onnx")
        assert recognizer.match_threshold == 0.363

    def test_extract_embedding_stub_fallback(self) -> None:
        recognizer = FaceRecognizer(model_path="non_existent.onnx")
        dummy_crop = np.zeros((100, 100, 3), dtype=np.uint8)
        emb = recognizer.extract_embedding(dummy_crop)
        assert isinstance(emb, np.ndarray)
        assert emb.shape == (128,)

    def test_match_method(self) -> None:
        recognizer = FaceRecognizer(model_path="non_existent.onnx", match_threshold=0.363)
        emb1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        emb2 = np.array([0.9, 0.1, 0.0], dtype=np.float32)
        sim, is_same = recognizer.match(emb1, emb2)
        assert sim > 0.8
        assert is_same is True


class TestLoadDatabase:
    """Test suite for employee JSON database loading."""

    def test_load_non_existent_file(self) -> None:
        db = load_database("non_existent_path.json")
        assert db == []

    def test_load_valid_file(self) -> None:
        records = [
            {"id": "E1", "name": "Test User", "role": "Dev", "embedding": [0.1, 0.2]}
        ]
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
            json.dump(records, f)
            temp_path = f.name

        try:
            db = load_database(temp_path)
            assert len(db) == 1
            assert db[0]["name"] == "Test User"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
