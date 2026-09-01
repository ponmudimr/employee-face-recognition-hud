"""Main real-time face recognition HUD pipeline orchestrator for Arduino UNO Q / ARM Cortex-A53."""

import argparse
import atexit
import logging
import signal
import sys
import time
from typing import List, Dict, Any, Optional
import cv2
import numpy as np

from capture import WebcamCapture, DisplayWindow
from detect import FaceDetector
from recognize import FaceRecognizer, load_database, match_face, DEFAULT_MATCH_THRESHOLD
from overlay import draw_overlay

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("HUD-Main")


def create_opencv_tracker() -> Optional[Any]:
    """Factory helper to create an OpenCV face tracker (CSRT or KCF) across OpenCV versions.

    Returns:
        Tracker instance or None if tracking module unavailable in OpenCV build.
    """
    tracker_factories = [
        getattr(cv2, "TrackerKCF_create", None),
        getattr(cv2, "TrackerCSRT_create", None),
        getattr(getattr(cv2, "legacy", None), "TrackerKCF_create", None),
    ]

    for factory in tracker_factories:
        if factory is not None:
            try:
                return factory()
            except Exception:
                pass

    logger.warning("OpenCV tracker factory unavailable in current cv2 build; tracking fallback active.")
    return None


class PipelineManager:
    """Orchestrates video capture, downscaled detection, embedding recognition, object tracking, and HUD output."""

    def __init__(
        self,
        camera_index: int = 0,
        db_path: str = "enrollment/database/employees.json",
        detect_interval: int = 3,
        similarity_threshold: float = DEFAULT_MATCH_THRESHOLD,
        no_display: bool = False
    ) -> None:
        """Initialize pipeline components.

        Args:
            camera_index: V4L2 device index for webcam.
            db_path: Path to employee JSON database.
            detect_interval: Run detection & embedding extraction every N frames.
            similarity_threshold: Cosine similarity cutoff score.
            no_display: Force headless execution without GUI display window.
        """
        self.camera_index = camera_index
        self.db_path = db_path
        self.detect_interval = max(1, detect_interval)
        self.similarity_threshold = similarity_threshold
        self.no_display = no_display

        self.cap = WebcamCapture(device_index=self.camera_index)
        self.display = DisplayWindow(fullscreen=True) if not self.no_display else None
        self.detector = FaceDetector()
        self.recognizer = FaceRecognizer()

        self.database: List[Dict[str, Any]] = []
        self.tracked_faces: List[Dict[str, Any]] = []
        self.trackers: List[Any] = []

    def start(self) -> None:
        """Execute the real-time face recognition pipeline loop."""
        logger.info("Initializing Employee Face Recognition HUD system...")

        # Load database
        self.database = load_database(self.db_path)
        logger.info(f"Database contains {len(self.database)} enrolled employee record(s).")

        # Open webcam capture
        if not self.cap.open():
            logger.critical(
                f"BOARD BRINGUP ERROR: Video device /dev/video{self.camera_index} is unavailable. "
                "Check USB webcam connection, power, and kernel V4L2 drivers."
            )
            sys.exit(1)

        # Register robust cleanup handlers for exit / SIGINT / SIGTERM
        def _on_signal(signum, frame):
            logger.info(f"Signal {signum} received. Cleaning up hardware resources...")
            self.cleanup()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _on_signal)
            signal.signal(signal.SIGTERM, _on_signal)
        except (ValueError, Exception):
            pass
        atexit.register(self.cleanup)

        # Initialize display if not headless mode
        if self.display is not None:
            if not self.display.create():
                logger.warning(
                    "DISPLAY BRINGUP WARNING: HDMI/USB-C AR Glass display window could not be opened. "
                    "Continuing in headless frame processing mode."
                )
                self.display = None

        frame_count = 0
        start_time = time.time()
        fps = 0.0

        logger.info("Pipeline loop started. Press 'q' or Ctrl+C to stop.")

        try:
            while True:
                loop_start = time.time()
                ret, frame = self.cap.read()

                if not ret or frame is None:
                    logger.error("Webcam read timeout or disconnected. Waiting for stream recovery...")
                    time.sleep(0.5)
                    continue

                frame_count += 1

                # Step 1: Detect & Recognize every N frames; Track in between
                if frame_count % self.detect_interval == 0 or not self.tracked_faces:
                    self._run_detection_and_recognition(frame)
                else:
                    self._run_tracking(frame)

                # Step 2: Calculate real-time FPS
                elapsed = time.time() - start_time
                if elapsed >= 1.0:
                    fps = frame_count / elapsed
                    logger.info(f"Performance: {fps:.1f} FPS | Active Tracked Faces: {len(self.tracked_faces)}")
                    frame_count = 0
                    start_time = time.time()

                # Step 3: Draw HUD graphics overlay
                output_frame = draw_overlay(frame, self.tracked_faces, fps=fps)

                # Step 4: Output to HDMI/USB-C AR glass display window
                if self.display is not None:
                    self.display.show(output_frame)
                    key = self.display.poll_key(delay_ms=1)
                    if key == ord('q') or key == 27:  # 'q' or ESC
                        logger.info("Quit key received. Shutting down pipeline.")
                        break

        except KeyboardInterrupt:
            logger.info("Interrupt signal received. Exiting HUD pipeline.")
        finally:
            self.cleanup()

    def _run_detection_and_recognition(self, frame: np.ndarray) -> None:
        """Execute face detection and embedding recognition step."""
        detections = self.detector.detect(frame)
        self.tracked_faces.clear()
        self.trackers.clear()

        img_h, img_w = frame.shape[:2]

        for face_det in detections:
            x, y, w, h, score = face_det
            # Clamp coordinates to frame boundaries
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(img_w, x + w), min(img_h, y + h)

            match_info = None

            if x2 > x1 and y2 > y1:
                embedding = self.recognizer.extract_embedding(frame, face_det)
                match_info = match_face(embedding, self.database, threshold=self.similarity_threshold)

            tracked_entry = {
                "bbox": (x1, y1, x2 - x1, y2 - y1),
                "match": match_info
            }

            # Initialize tracking object for non-detection frames
            tracker = create_opencv_tracker()
            if tracker is not None:
                try:
                    tracker.init(frame, (x1, y1, x2 - x1, y2 - y1))
                    self.trackers.append(tracker)
                except Exception as e:
                    logger.debug(f"Tracker init failed: {e}")
                    self.trackers.append(None)
            else:
                self.trackers.append(None)

            self.tracked_faces.append(tracked_entry)

    def _run_tracking(self, frame: np.ndarray) -> None:
        """Update bounding boxes using OpenCV CSRT/KCF tracker for frames between detections."""
        updated_faces = []
        updated_trackers = []

        for i, tracker in enumerate(self.trackers):
            face_data = self.tracked_faces[i]
            if tracker is not None:
                try:
                    success, box = tracker.update(frame)
                    if success:
                        x, y, w, h = [int(v) for v in box]
                        face_data["bbox"] = (x, y, w, h)
                        updated_faces.append(face_data)
                        updated_trackers.append(tracker)
                        continue
                except Exception as e:
                    logger.debug(f"Tracker update error: {e}")

            # Keep previous bbox if tracking failed
            updated_faces.append(face_data)
            updated_trackers.append(None)

        self.tracked_faces = updated_faces
        self.trackers = updated_trackers

    def cleanup(self) -> None:
        """Release hardware capture and display resources cleanly."""
        logger.info("Cleaning up pipeline hardware resources...")
        self.cap.release()
        if self.display is not None:
            self.display.close()
        logger.info("Shutdown complete.")


def main() -> None:
    """CLI entrypoint for real-time face recognition HUD."""
    parser = argparse.ArgumentParser(
        description="Real-Time Employee Face Recognition HUD for Arduino UNO Q (ARM Cortex-A53)"
    )
    parser.add_argument(
        "--camera", type=int, default=-1,
        help="Camera device index (-1 for OAK-D-Lite primary default, >=0 for V4L2 webcam)"
    )
    parser.add_argument(
        "--db", type=str, default="enrollment/database/employees.json",
        help="Path to employee JSON database file"
    )
    parser.add_argument(
        "--detect-interval", type=int, default=3,
        help="Interval N frames between running face detection models (default: 3)"
    )
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_MATCH_THRESHOLD,
        help=f"Cosine similarity threshold for employee recognition (default: {DEFAULT_MATCH_THRESHOLD})"
    )
    parser.add_argument(
        "--no-display", action="store_true",
        help="Disable HDMI/USB-C GUI window (headless mode)"
    )

    args = parser.parse_args()

    pipeline = PipelineManager(
        camera_index=args.camera,
        db_path=args.db,
        detect_interval=args.detect_interval,
        similarity_threshold=args.threshold,
        no_display=args.no_display
    )
    pipeline.start()


if __name__ == "__main__":
    main()
