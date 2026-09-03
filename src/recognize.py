"""Face embedding extraction and database cosine similarity matching module using OpenCV SFace ONNX model."""

import argparse
import json
import logging
import os
import sys
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Cosine similarity threshold for SFace (original was 0.363, lowered to 0.30 for better tolerance)
DEFAULT_MATCH_THRESHOLD = 0.60


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two 1D embedding vectors.

    Args:
        v1: First embedding vector (1D numpy array).
        v2: Second embedding vector (1D numpy array).

    Returns:
        float: Cosine similarity score in range [-1.0, 1.0].
    """
    if v1 is None or v2 is None:
        return 0.0

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
    threshold: float = DEFAULT_MATCH_THRESHOLD
) -> Optional[Dict[str, Any]]:
    """Match a target face embedding against stored database embeddings using cosine similarity.

    Args:
        embedding: Target face embedding vector (1D numpy array).
        database: List of employee records loaded from JSON database.
        threshold: Minimum cosine similarity required to confirm match (default: 0.363 for SFace).

    Returns:
        Dictionary containing matched employee record and similarity score, or None if no match.
    """
    if embedding is None or len(database) == 0:
        return None

    # Check if target embedding is zero vector (stub or missing face)
    if np.linalg.norm(embedding) == 0.0:
        return None

    best_match: Optional[Dict[str, Any]] = None
    best_similarity: float = -1.0

    for record in database:
        db_emb = record.get("embedding")
        if db_emb is None:
            continue

        db_emb_array = np.array(db_emb, dtype=np.float32)
        sim = cosine_similarity(embedding, db_emb_array)
        
        logger.debug(f"  vs {record.get('name', 'Unknown')}: score={sim:.3f}")

        if sim > best_similarity:
            best_similarity = sim
            best_match = record
            
    if best_match is not None:
        logger.info(f"Live match: {best_match.get('name', 'Unknown')} score={best_similarity:.3f} (threshold={threshold:.2f})")

    if best_match is not None and best_similarity >= threshold:
        match_info = dict(best_match)
        match_info["similarity"] = best_similarity
        return match_info

    return None


class FaceRecognizer:
    """Extracts 128-dimensional feature embeddings from faces using OpenCV's SFace ONNX model."""

    def __init__(
        self,
        model_path: str = "models/face_recognition_sface.onnx",
        match_threshold: float = DEFAULT_MATCH_THRESHOLD
    ) -> None:
        """Initialize SFace recognizer parameters.

        Args:
            model_path: Path to SFace ONNX model file.
            match_threshold: Default cosine similarity match threshold.
        """
        self.model_path = model_path
        self.match_threshold = match_threshold
        self.recognizer: Optional[Any] = None
        self._is_loaded = False

    def load_model(self) -> bool:
        """Load the SFace ONNX model into memory.

        Returns:
            bool: True if model loaded successfully, False otherwise.
        """
        if not os.path.exists(self.model_path):
            logger.warning(
                f"Face recognition model file not found at '{self.model_path}'. "
                "Download it using: curl -L -o models/face_recognition_sface.onnx "
                "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
            )
            self._is_loaded = False
            return False

        try:
            if hasattr(cv2, "FaceRecognizerSF"):
                self.recognizer = cv2.FaceRecognizerSF.create(
                    self.model_path,
                    "",
                    cv2.dnn.DNN_BACKEND_OPENCV,
                    cv2.dnn.DNN_TARGET_CPU
                )
                self._is_loaded = True
                logger.info(f"SFace recognizer model loaded successfully from '{self.model_path}'.")
                return True
            else:
                logger.error("OpenCV build does not contain cv2.FaceRecognizerSF support.")
                self._is_loaded = False
                return False
        except Exception as e:
            logger.error(f"Failed to load SFace model from '{self.model_path}': {e}")
            self._is_loaded = False
            return False

    def align_crop(self, frame: np.ndarray, face_info: Any) -> Optional[np.ndarray]:
        """Align and crop face image using 5-point landmarks or raw YuNet detection array.

        Args:
            frame: BGR full image frame.
            face_info: `DetectedFace` instance, raw 15-element YuNet array, or face crop.

        Returns:
            Aligned BGR face crop array of shape (112, 112, 3), or None.
        """
        if frame is None or frame.size == 0:
            return None

        if not self._is_loaded:
            self.load_model()

        # Extract raw_face array if face_info is a DetectedFace instance
        raw_face = getattr(face_info, "raw_face", face_info)

        if self.recognizer is not None and isinstance(raw_face, np.ndarray) and raw_face.shape == (15,):
            try:
                aligned = self.recognizer.alignCrop(frame, raw_face)
                return aligned
            except Exception as e:
                logger.debug(f"SFace alignCrop failed: {e}")

        # Fallback bounding box crop & resize if alignCrop is unavailable
        if hasattr(face_info, "bbox"):
            x, y, w, h = face_info.bbox
        elif isinstance(face_info, (tuple, list)) and len(face_info) >= 4:
            x, y, w, h = face_info[:4]
        else:
            return cv2.resize(face_info, (112, 112)) if (face_info is not None and face_info.size > 0) else None

        img_h, img_w = frame.shape[:2]
        x1, y1 = max(0, int(x)), max(0, int(y))
        x2, y2 = min(img_w, int(x + w)), min(img_h, int(y + h))

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        return cv2.resize(crop, (112, 112))

    def extract_embedding(self, face_or_frame: np.ndarray, face_info: Optional[Any] = None) -> np.ndarray:
        """Extract a 1D normalized 128-dimensional feature embedding vector.

        Args:
            face_or_frame: BGR frame image (if face_info provided) or cropped face image.
            face_info: Optional `DetectedFace` instance or detection info.

        Returns:
            Normalized 1D embedding vector (numpy array of shape (128,)).
        """
        if face_or_frame is None or face_or_frame.size == 0:
            return np.zeros(128, dtype=np.float32)

        if not self._is_loaded:
            self.load_model()

        aligned_face: Optional[np.ndarray] = None

        if face_info is not None:
            aligned_face = self.align_crop(face_or_frame, face_info)
        else:
            # face_or_frame is treated as a face crop
            if face_or_frame.shape[:2] == (112, 112):
                aligned_face = face_or_frame
            else:
                aligned_face = cv2.resize(face_or_frame, (112, 112))

        if aligned_face is not None and self.recognizer is not None:
            try:
                feat = self.recognizer.feature(aligned_face)
                emb = feat.flatten().astype(np.float32)
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                return emb
            except Exception as e:
                logger.error(f"Error during SFace feature extraction: {e}")

        # Return dummy 128-d zero vector if model missing or extraction fails
        return np.zeros(128, dtype=np.float32)

    def match(self, emb1: np.ndarray, emb2: np.ndarray) -> Tuple[float, bool]:
        """Compare two 128-d embedding vectors.

        Args:
            emb1: First embedding vector.
            emb2: Second embedding vector.

        Returns:
            Tuple containing cosine similarity score and boolean match verdict.
        """
        sim = cosine_similarity(emb1, emb2)
        is_same = sim >= self.match_threshold
        return sim, is_same


def main() -> None:
    """CLI standalone test path for comparing face embeddings between two static images."""
    parser = argparse.ArgumentParser(description="Standalone SFace Face Recognition CLI Demo")
    parser.add_argument("img1_path", type=str, help="Path to first face image (JPG/PNG)")
    parser.add_argument("img2_path", type=str, help="Path to second face image (JPG/PNG)")
    parser.add_argument("--det-model", type=str, default="models/face_detection_yunet.onnx", help="YuNet detector model path")
    parser.add_argument("--rec-model", type=str, default="models/face_recognition_sface.onnx", help="SFace recognizer model path")
    parser.add_argument("--threshold", type=float, default=DEFAULT_MATCH_THRESHOLD, help="Cosine similarity match threshold")
    args = parser.parse_args()

    # Import detector for standalone demo
    from detect import FaceDetector

    img1 = cv2.imread(args.img1_path)
    img2 = cv2.imread(args.img2_path)

    if img1 is None:
        print(f"Error: Could not read image 1 at '{args.img1_path}'.")
        sys.exit(1)
    if img2 is None:
        print(f"Error: Could not read image 2 at '{args.img2_path}'.")
        sys.exit(1)

    detector = FaceDetector(model_path=args.det_model, target_size=None)
    recognizer = FaceRecognizer(model_path=args.rec_model, match_threshold=args.threshold)

    faces1 = detector.detect(img1)
    faces2 = detector.detect(img2)

    if not faces1:
        print(f"Error: No face detected in image 1 ('{args.img1_path}').")
        sys.exit(1)
    if not faces2:
        print(f"Error: No face detected in image 2 ('{args.img2_path}').")
        sys.exit(1)

    face1 = faces1[0]
    face2 = faces2[0]

    emb1 = recognizer.extract_embedding(img1, face1)
    emb2 = recognizer.extract_embedding(img2, face2)

    sim, is_same = recognizer.match(emb1, emb2)

    print("=== SFace Face Comparison Results ===")
    print(f"Image 1: '{args.img1_path}' (Face bbox: {face1.bbox}, Score: {face1.score:.3f})")
    print(f"Image 2: '{args.img2_path}' (Face bbox: {face2.bbox}, Score: {face2.score:.3f})")
    print(f"Cosine Similarity Score: {sim:.4f} (Threshold: {args.threshold})")
    verdict = "SAME PERSON" if is_same else "DIFFERENT PEOPLE"
    print(f"Verdict: {verdict}")


if __name__ == "__main__":
    main()
