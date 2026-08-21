"""Face embedding extraction and database cosine similarity matching module."""

import json
import logging
import os
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two 1D embedding vectors.

    Args:
        v1: First embedding vector (1D numpy array).
        v2: Second embedding vector (1D numpy array).

    Returns:
        float: Cosine similarity score in range [-1.0, 1.0].
    """
    v1_flat = np.asarray(v1, dtype=np.float32).flatten()
    v2_flat = np.asarray(v2, dtype=np.float32).flatten()

    norm1 = np.linalg.norm(v1_flat)
    norm2 = np.linalg.norm(v2_flat)

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    sim = float(np.dot(v1_flat, v2_flat) / (norm1 * norm2))
    return float(np.clip(sim, -1.0, 1.0))


def load_database(db_path: str = "enrollment/database/employees.json") -> List[Dict[str, Any]]:
    """Load employee records and embeddings from a local JSON database.

    Args:
        db_path: Filepath to the JSON employee database.

    Returns:
        List of employee dictionaries containing id, name, role, and embedding vector.
    """
    if not os.path.exists(db_path):
        logger.warning(f"Employee database file not found at '{db_path}'. Returning empty database.")
        return []

    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                logger.info(f"Loaded {len(data)} employee records from '{db_path}'.")
                return data
            logger.error(f"Invalid database format in '{db_path}'. Expected JSON list.")
            return []
    except Exception as e:
        logger.error(f"Failed to read database file '{db_path}': {e}")
        return []


def match_face(
    embedding: np.ndarray,
    database: List[Dict[str, Any]],
    threshold: float = 0.5
) -> Optional[Dict[str, Any]]:
    """Match a target face embedding against stored database embeddings using cosine similarity.

    Args:
        embedding: Target face embedding vector (1D numpy array).
        database: List of employee records loaded from JSON database.
        threshold: Minimum cosine similarity required to confirm match.

    Returns:
        Dictionary containing matched employee record and similarity score, or None if no match.
    """
    if embedding is None or len(database) == 0:
        return None

    best_match: Optional[Dict[str, Any]] = None
    best_similarity: float = -1.0

    for record in database:
        db_emb = record.get("embedding")
        if db_emb is None:
            continue

        db_emb_array = np.array(db_emb, dtype=np.float32)
        sim = cosine_similarity(embedding, db_emb_array)

        if sim > best_similarity:
            best_similarity = sim
            best_match = record

    if best_match is not None and best_similarity >= threshold:
        match_info = dict(best_match)
        match_info["similarity"] = best_similarity
        return match_info

    return None


class FaceRecognizer:
    """Extracts feature embeddings from cropped face images using lightweight ONNX neural net."""

    def __init__(self, model_path: Optional[str] = "models/face_recognition_sface.onnx") -> None:
        """Initialize face recognizer model parameters.

        Args:
            model_path: Path to ONNX face feature embedding model.
        """
        self.model_path = model_path
        self._is_loaded = False

    def load_model(self) -> bool:
        """Load feature extraction ONNX model.

        Returns:
            bool: True if model loaded successfully.
        """
        # TODO: Implement ONNX Runtime or cv2.FaceRecognizerSF model initialization
        # Example for SFace:
        # self.model = cv2.FaceRecognizerSF.create(self.model_path, "")
        logger.info(f"TODO: Load face recognition model from '{self.model_path}'.")
        self._is_loaded = True
        return True

    def extract_embedding(self, face_crop: np.ndarray) -> np.ndarray:
        """Extract a 1D normalized feature embedding vector from a cropped face image.

        Args:
            face_crop: Cropped BGR face image numpy array.

        Returns:
            Normalized 1D embedding vector (numpy array). Stub returns zeros vector.
        """
        if face_crop is None or face_crop.size == 0:
            return np.zeros(128, dtype=np.float32)

        if not self._is_loaded:
            self.load_model()

        # TODO: Preprocess cropped face (align, resize to 112x112, normalize)
        # TODO: Perform forward pass through ONNX model: embedding = self.model.feature(aligned_face)

        # Return dummy 128-d zero vector until ONNX model is integrated
        return np.zeros(128, dtype=np.float32)
