"""Face detection module optimized for ARM Cortex-A53 using OpenCV YuNet ONNX model."""

import argparse
import logging
import os
import sys
from typing import List, Tuple, Optional, Any
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class DetectedFace:
    """Represents a detected face result containing bounding box, confidence score, and 5-point facial landmarks."""

    def __init__(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        score: float,
        landmarks: Optional[np.ndarray] = None,
        raw_face: Optional[np.ndarray] = None
    ) -> None:
        """Initialize face detection result.

        Args:
            x: Bounding box left x-coordinate.
            y: Bounding box top y-coordinate.
            w: Bounding box width.
            h: Bounding box height.
            score: Detection confidence score (0.0 to 1.0).
            landmarks: 5-point facial landmark coordinates array of shape (5, 2).
            raw_face: Raw 15-element YuNet detection array [x, y, w, h, x_re, y_re, ..., score].
        """
        self.x = int(x)
        self.y = int(y)
        self.w = int(w)
        self.h = int(h)
        self.score = float(score)
        self.landmarks = landmarks if landmarks is not None else np.zeros((5, 2), dtype=np.float32)
        self.raw_face = raw_face if raw_face is not None else np.zeros(15, dtype=np.float32)

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        """Get bounding box tuple (x, y, w, h)."""
        return (self.x, self.y, self.w, self.h)

    def __getitem__(self, idx: int) -> Any:
        """Support 5-tuple indexing for backward compatibility (x, y, w, h, score)."""
        return (self.x, self.y, self.w, self.h, self.score)[idx]

    def __iter__(self):
        """Support 5-tuple unpacking: `x, y, w, h, score = face`."""
        return iter((self.x, self.y, self.w, self.h, self.score))

    def __len__(self) -> int:
        """Return tuple length for unpacking."""
        return 5

    def __repr__(self) -> str:
        return f"DetectedFace(bbox=({self.x}, {self.y}, {self.w}, {self.h}), score={self.score:.3f})"


class FaceDetector:
    """Lightweight face detector wrapper using OpenCV's built-in YuNet ONNX model.

    Frame downscaling can be applied prior to detection to preserve CPU cycles on ARM Cortex-A53 platforms.
    """

    def __init__(
        self,
        model_path: str = "models/face_detection_yunet.onnx",
        confidence_threshold: float = 0.45,
        nms_threshold: float = 0.3,
        target_size: Optional[Tuple[int, int]] = (640, 480)
    ) -> None:
        """Initialize YuNet face detector configuration.

        Args:
            model_path: Path to YuNet ONNX model weights.
            confidence_threshold: Minimum detection score threshold (0.0 to 1.0).
            nms_threshold: Non-maximum suppression threshold.
            target_size: Optional (width, height) downscaled resolution for fast ARM inference.
                         If None, detects on full frame resolution.
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.target_size = target_size
        self.net: Optional[Any] = None
        self._is_loaded = False
        self._current_input_size: Optional[Tuple[int, int]] = None

    def load_model(self, initial_input_size: Tuple[int, int] = (320, 240)) -> bool:
        """Load the YuNet ONNX face detector model into memory.

        Args:
            initial_input_size: Initial (width, height) input resolution for detector.

        Returns:
            bool: True if model loaded successfully, False otherwise.
        """
        if not os.path.exists(self.model_path):
            logger.warning(
                f"Face detection model file not found at '{self.model_path}'. "
                "Download it using: curl -L -o models/face_detection_yunet.onnx "
                "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
            )
            self._is_loaded = False
            return False

        try:
            if hasattr(cv2, "FaceDetectorYN"):
                self.net = cv2.FaceDetectorYN.create(
                    self.model_path,
                    "",
                    initial_input_size,
                    self.confidence_threshold,
                    self.nms_threshold,
                    5000,
                    cv2.dnn.DNN_BACKEND_OPENCV,
                    cv2.dnn.DNN_TARGET_OPENCL
                )
                self._current_input_size = initial_input_size
                self._is_loaded = True
                logger.info(f"YuNet face detector loaded successfully from '{self.model_path}'.")
                return True
            else:
                logger.error("OpenCV build does not contain cv2.FaceDetectorYN support.")
                self._is_loaded = False
                return False
        except Exception as e:
            logger.error(f"Failed to load YuNet model from '{self.model_path}': {e}")
            self._is_loaded = False
            return False

    def detect(self, frame: np.ndarray) -> List[DetectedFace]:
        """Detect faces in a BGR image frame using YuNet.

        Applies frame downscaling if target_size is configured to reduce latency on ARM Cortex-A53,
        then rescales coordinates back to original frame dimensions.

        Args:
            frame: Input image array (BGR format).

        Returns:
            List of `DetectedFace` objects, each exposing (x, y, w, h, score) and facial landmarks.
        """
        if frame is None or frame.size == 0:
            return []

        orig_h, orig_w = frame.shape[:2]

        if not self._is_loaded:
            if not self.load_model(initial_input_size=(orig_w, orig_h)):
                return []

        if self.net is None:
            return []

        # Determine processing resolution (downscaled or full)
        if self.target_size is not None and self.target_size[0] > 0 and self.target_size[1] > 0:
            proc_w, proc_h = self.target_size
            proc_frame = cv2.resize(frame, (proc_w, proc_h))
            scale_x = orig_w / float(proc_w)
            scale_y = orig_h / float(proc_h)
        else:
            proc_w, proc_h = orig_w, orig_h
            proc_frame = frame
            scale_x = 1.0
            scale_y = 1.0

        # Update model input size if frame dimensions changed
        if self._current_input_size != (proc_w, proc_h):
            self.net.setInputSize((proc_w, proc_h))
            self._current_input_size = (proc_w, proc_h)

        try:
            results = self.net.detect(proc_frame)
            if isinstance(results, tuple):
                _, faces = results
            else:
                faces = results

            if faces is None or len(faces) == 0:
                return []

            detected_faces: List[DetectedFace] = []
            for face in faces:
                # YuNet output layout (15 values):
                # [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rc, y_rc, x_lc, y_lc, score]
                raw_face_orig = face.astype(np.float32).copy()

                # Scale bounding box and landmark points back to original image dimensions
                x = int(round(face[0] * scale_x))
                y = int(round(face[1] * scale_y))
                w = int(round(face[2] * scale_x))
                h = int(round(face[3] * scale_y))
                score = float(face[14])

                raw_face_orig[0] = x
                raw_face_orig[1] = y
                raw_face_orig[2] = w
                raw_face_orig[3] = h

                landmarks_raw = face[4:14].reshape((5, 2))
                landmarks_orig = landmarks_raw * np.array([scale_x, scale_y], dtype=np.float32)

                for i in range(5):
                    raw_face_orig[4 + i * 2] = landmarks_orig[i, 0]
                    raw_face_orig[5 + i * 2] = landmarks_orig[i, 1]

                det = DetectedFace(
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    score=score,
                    landmarks=landmarks_orig,
                    raw_face=raw_face_orig
                )
                detected_faces.append(det)

            return detected_faces

        except Exception as e:
            logger.error(f"Error during YuNet face detection: {e}")
            return []


def main() -> None:
    """CLI standalone test path for verifying face detection on a static image file."""
    parser = argparse.ArgumentParser(description="Standalone YuNet Face Detection CLI Demo")
    parser.add_argument("image_path", type=str, help="Path to input image file (JPG/PNG)")
    parser.add_argument("--model", type=str, default="models/face_detection_yunet.onnx", help="Path to YuNet ONNX model")
    parser.add_argument("--threshold", type=float, default=0.6, help="Confidence score threshold")
    args = parser.parse_args()

    if not os.path.exists(args.image_path):
        print(f"Error: Input image file '{args.image_path}' does not exist.")
        sys.exit(1)

    image = cv2.imread(args.image_path)
    if image is None:
        print(f"Error: Could not read image at '{args.image_path}'.")
        sys.exit(1)

    detector = FaceDetector(model_path=args.model, confidence_threshold=args.threshold, target_size=None)
    faces = detector.detect(image)

    print(f"=== Detection Results for '{args.image_path}' ===")
    print(f"Total faces detected: {len(faces)}")
    for i, face in enumerate(faces):
        print(f"  Face {i+1}: Bounding Box = (x={face.x}, y={face.y}, w={face.w}, h={face.h}), Confidence = {face.score:.4f}")
        print(f"          Landmarks (5-point):")
        labels = ["Right Eye", "Left Eye ", "Nose Tip ", "R Mouth  ", "L Mouth  "]
        for j, (lx, ly) in enumerate(face.landmarks):
            print(f"            - {labels[j]}: ({lx:.1f}, {ly:.1f})")


if __name__ == "__main__":
    main()
