"""Industrial machine/PLC identification via ArUco fiducial markers, using OpenCV's built-in aruco module.

Mirrors the face detect/recognize split in detect.py + recognize.py: a marker sticker on a
machine plays the same role a face does for a person — detect its presence in frame, then
look up which machine it identifies in a local JSON registry (machinery/database/machines.json).
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_ARUCO_DICT = cv2.aruco.DICT_4X4_50


class DetectedMarker:
    """Represents a detected ArUco marker: its ID and the four corner points OpenCV found."""

    def __init__(self, marker_id: int, corners: np.ndarray) -> None:
        """
        Args:
            marker_id: Decoded marker ID (matches a `marker_id` entry in machines.json).
            corners: (4, 2) array of the marker's four corner points in the original frame.
        """
        self.marker_id = int(marker_id)
        self.corners = corners

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        """Axis-aligned bounding box `(x, y, w, h)` enclosing the marker's four corners."""
        xs = self.corners[:, 0]
        ys = self.corners[:, 1]
        x1, y1 = int(xs.min()), int(ys.min())
        x2, y2 = int(xs.max()), int(ys.max())
        return (x1, y1, x2 - x1, y2 - y1)

    def __repr__(self) -> str:
        return f"DetectedMarker(id={self.marker_id}, bbox={self.bbox})"


class MachineDetector:
    """Lightweight ArUco marker detector wrapper.

    Chosen over a trained object detector or QR codes: markers stay reliably decodable at
    odd viewing angles and motion blur (the exact conditions a moving AR headset sees), and
    detection cost is a few milliseconds on CPU — negligible next to the ~200ms YuNet pass
    already running per detection cycle.
    """

    def __init__(self, dictionary: int = DEFAULT_ARUCO_DICT) -> None:
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)

    def detect(self, frame: np.ndarray) -> List[DetectedMarker]:
        """Detect all ArUco markers visible in a BGR frame.

        Args:
            frame: Input image array (BGR format).

        Returns:
            List of `DetectedMarker` objects, one per marker found.
        """
        if frame is None or frame.size == 0:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        try:
            corners, ids, _ = self.detector.detectMarkers(gray)
        except Exception as e:
            logger.error(f"Error during ArUco marker detection: {e}")
            return []

        if ids is None or len(ids) == 0:
            return []

        # `ids` is a flat (N,) array in current OpenCV (was (N,1) in older
        # versions) -- flatten defensively so this works across builds.
        ids = np.asarray(ids).flatten()

        return [
            DetectedMarker(marker_id=ids[i], corners=corners[i].reshape(4, 2))
            for i in range(len(ids))
        ]


def load_machine_database(db_path: str = "machinery/database/machines.json") -> List[Dict[str, Any]]:
    """Load registered machine records from a local JSON database.

    Args:
        db_path: Filepath to the JSON machine database.

    Returns:
        List of machine dictionaries, each containing marker_id, name, and api_base_url.
    """
    if not os.path.exists(db_path):
        logger.warning(f"Machine database file not found at '{db_path}'. Returning empty database.")
        return []

    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                logger.info(f"Loaded {len(data)} machine record(s) from '{db_path}'.")
                return data
            logger.error(f"Invalid database format in '{db_path}'. Expected JSON list.")
            return []
    except Exception as e:
        logger.error(f"Failed to read machine database file '{db_path}': {e}")
        return []


def match_machine(marker_id: int, database: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Look up which registered machine a decoded marker ID belongs to.

    Args:
        marker_id: Decoded ArUco marker ID.
        database: List of machine records loaded from the JSON database.

    Returns:
        The matching machine record, or None if no registered machine uses this marker ID.
    """
    for record in database:
        if int(record.get("marker_id", -1)) == int(marker_id):
            return record
    return None
