import cv2
cv2.setNumThreads(4)
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
    return cv2.legacy.TrackerMOSSE_create() if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerMOSSE_create") else cv2.TrackerKCF_create() if hasattr(cv2, "TrackerKCF_create") else None
class PipelineManager:
    """Orchestrates video capture, downscaled detection, embedding recognition, object tracking, and HUD output."""

    def __init__(
        self,
        camera_index: int = 0,
        db_path: str = "enrollment/database/employees.json",
        detect_interval: int = 3,
        similarity_threshold: float = DEFAULT_MATCH_THRESHOLD,
        max_faces: int = 3,
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
        self.max_faces = max_faces
        self.no_display = no_display

        self.cap = WebcamCapture(device_index=self.camera_index)
        self.display = DisplayWindow(fullscreen=True) if not self.no_display else None
        
        # Lowered confidence threshold from 0.45 to 0.35 to improve detection in poor lighting
        self.detector = FaceDetector(confidence_threshold=0.35)
        self.recognizer = FaceRecognizer(match_threshold=self.similarity_threshold)

        self.database: List[Dict[str, Any]] = []
        self.tracked_faces: List[Dict[str, Any]] = []
        self.trackers: List[Any] = []
        self.pipeline_frame_count = 0

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


        self.prof_read = []
        self.prof_det = []
        self.prof_rec = []
        self.prof_trk = []
        self.prof_draw = []
        self.prof_disp = []
        self.det_count = 0
        self.trk_count = 0

        try:
            while True:
                t_start = time.perf_counter()
                
                t0 = time.perf_counter()
                ret, frame = self.cap.read()
                t1 = time.perf_counter()
                self.prof_read.append((t1 - t0) * 1000)

                if not ret or frame is None:
                    logger.error("Webcam read timeout or disconnected. Waiting for stream recovery...")
                    time.sleep(0.5)
                    continue

                frame_count += 1

                # Step 1: Detect & Recognize every N frames; Track in between
                self.pipeline_frame_count += 1
                if self.pipeline_frame_count % self.detect_interval == 0 or not self.tracked_faces:
                    self.det_count += 1
                    t0 = time.perf_counter()
                    
                    detections = self.detector.detect(frame)
                    if detections:
                        # Cap to N largest faces to bound maximum CPU time (Option A)
                        detections = sorted(detections, key=lambda d: d.w * d.h, reverse=True)[:self.max_faces]
                    t_det_end = time.perf_counter()
                    self.prof_det.append((t_det_end - t0) * 1000)
                    
                    self.tracked_faces.clear()
                    self.trackers.clear()
                    img_h, img_w = frame.shape[:2]
                    
                    for face_det in detections:
                        x, y, w, h, score = face_det
                        x1, y1 = max(0, x), max(0, y)
                        x2, y2 = min(img_w, x + w), min(img_h, y + h)
                        match_info = None
                        if x2 > x1 and y2 > y1:
                            t_rec_start = time.perf_counter()
                            embedding = self.recognizer.extract_embedding(frame, face_det)
                            match_info = match_face(embedding, self.database, threshold=self.similarity_threshold)
                            self.prof_rec.append((time.perf_counter() - t_rec_start) * 1000)
                        
                        tracked_entry = {"bbox": (x1, y1, x2 - x1, y2 - y1), "match": match_info}
                        tracker = create_opencv_tracker()
                        if tracker is not None:
                            try:
                                tracker.init(frame, (x1, y1, x2 - x1, y2 - y1))
                                self.trackers.append(tracker)
                            except Exception as e:
                                self.trackers.append(None)
                        else:
                            self.trackers.append(None)
                        self.tracked_faces.append(tracked_entry)
                        
                else:
                    self.trk_count += 1
                    t0 = time.perf_counter()
                    self._run_tracking(frame)
                    self.prof_trk.append((time.perf_counter() - t0) * 1000)

                # Step 2: Calculate real-time FPS
                elapsed = time.time() - start_time
                if elapsed >= 1.0:
                    fps = frame_count / elapsed
                    frame_count = 0
                    start_time = time.time()
                    
                    if len(self.prof_read) >= 30:
                        logger.info(f"--- PROFILING OVER 30 FRAMES ---")
                        def p_stat(name, arr):
                            if not arr: return "N/A"
                            return f"min: {min(arr):.1f}ms | max: {max(arr):.1f}ms | avg: {sum(arr)/len(arr):.1f}ms"
                        logger.info(f"READ:  {p_stat('READ', self.prof_read)}")
                        logger.info(f"DET :  {p_stat('DET', self.prof_det)}")
                        logger.info(f"REC :  {p_stat('REC', self.prof_rec)}")
                        logger.info(f"TRK :  {p_stat('TRK', self.prof_trk)}")
                        logger.info(f"DRAW:  {p_stat('DRAW', self.prof_draw)}")
                        logger.info(f"DISP:  {p_stat('DISP', self.prof_disp)}")
                        logger.info(f"COUNTS -> Detects: {self.det_count} | Tracks: {self.trk_count}")
                        self.prof_read.clear(); self.prof_det.clear(); self.prof_rec.clear()
                        self.prof_trk.clear(); self.prof_draw.clear(); self.prof_disp.clear()
                        self.det_count = 0; self.trk_count = 0

                # Step 3: Draw HUD graphics overlay
                t0 = time.perf_counter()
                output_frame = draw_overlay(frame, self.tracked_faces, fps=fps)
                self.prof_draw.append((time.perf_counter() - t0) * 1000)

                # Step 4: Output to display
                t0 = time.perf_counter()
                if self.display is not None:
                    self.display.show(output_frame)
                    key = self.display.poll_key(delay_ms=1)
                    if key == ord('q') or key == 27:
                        break
                self.prof_disp.append((time.perf_counter() - t0) * 1000)
                
                # We stop after 150 frames to simulate 15 seconds at 10 fps or something
                # Or just run for 15 seconds
                
        except KeyboardInterrupt:
            logger.info("Interrupt signal received. Exiting HUD pipeline.")
        finally:
            self.cleanup()

    def _run_detection_and_recognition(self, frame: np.ndarray) -> None:
        """Execute face detection and embedding recognition step."""
        detections = self.detector.detect(frame)
        if detections:
            # Cap to N largest faces to bound maximum CPU time (Option A)
            detections = sorted(detections, key=lambda d: d.w * d.h, reverse=True)[:self.max_faces]
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
                    else:
                        logger.debug(f"Tracker update FAILED for face at frame {self.pipeline_frame_count}")
                except Exception as e:
                    logger.debug(f"Tracker update error: {e}")
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
        "--max-faces", type=int, default=3,
        help="Maximum number of largest faces to track simultaneously to maintain FPS (default: 3)"
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
        max_faces=args.max_faces,
        no_display=args.no_display
    )
    pipeline.start()


if __name__ == "__main__":
    main()
