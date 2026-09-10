import cv2
cv2.setNumThreads(4)
"""Main real-time face recognition HUD pipeline orchestrator for Arduino UNO Q / ARM Cortex-A53."""

import argparse
import atexit
import logging
import signal
import sys
import time
import threading
from typing import List, Dict, Any, Optional
import cv2
import numpy as np

from capture import WebcamCapture, DisplayWindow
from detect import FaceDetector
from recognize import FaceRecognizer, load_database, match_face, DEFAULT_MATCH_THRESHOLD
from machine_detect import MachineDetector, load_machine_database, match_machine
from machine_telemetry import MachineTelemetryClient
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

def calculate_iou(boxA, boxB):
    # box format: (x, y, w, h)
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])
    
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = boxA[2] * boxA[3]
    boxBArea = boxB[2] * boxB[3]
    
    if boxAArea + boxBArea - interArea == 0:
        return 0.0
    return interArea / float(boxAArea + boxBArea - interArea)

class PipelineManager:
    """Orchestrates video capture, downscaled detection, embedding recognition, object tracking, and HUD output."""

    def __init__(
        self,
        camera_index: int = 0,
        db_path: str = "enrollment/database/employees.json",
        machines_db_path: str = "machinery/database/machines.json",
        detect_interval: int = 3,
        similarity_threshold: float = DEFAULT_MATCH_THRESHOLD,
        max_faces: int = 3,
        no_display: bool = False,
        width: int = 640,
        height: int = 480
    ) -> None:
        """Initialize pipeline components.

        Args:
            camera_index: V4L2 device index for webcam.
            db_path: Path to employee JSON database.
            machines_db_path: Path to machine/PLC JSON database (ArUco marker registry).
            detect_interval: Run detection & embedding extraction every N frames.
            similarity_threshold: Cosine similarity cutoff score.
            no_display: Force headless execution without GUI display window.
        """
        self.camera_index = camera_index
        self.db_path = db_path
        self.machines_db_path = machines_db_path
        self.detect_interval = max(1, detect_interval)
        self.similarity_threshold = similarity_threshold
        self.max_faces = max_faces
        self.no_display = no_display

        self.cap = WebcamCapture(device_index=self.camera_index, width=width, height=height)
        self.display = DisplayWindow(fullscreen=True) if not self.no_display else None

        # 0.45 is YuNet's own standard default: 0.35 was tried and reverted
        # (caused false positives, see commit 332347e), 0.60 was too strict
        # and missed real faces. 0.45 is the validated middle ground.
        self.detector = FaceDetector(confidence_threshold=0.45, target_size=(width, height))
        self.recognizer = FaceRecognizer(match_threshold=self.similarity_threshold)
        self.machine_detector = MachineDetector()

        self.database: List[Dict[str, Any]] = []
        self.tracked_faces: List[Dict[str, Any]] = []
        self.trackers: List[Any] = []

        self.machine_database: List[Dict[str, Any]] = []
        self.tracked_machines: List[Dict[str, Any]] = []
        self.machine_trackers: List[Any] = []
        # One background telemetry poller per registered machine seen so far,
        # keyed by ArUco marker ID -- started lazily the first time its
        # marker is detected, then left running for the pipeline's lifetime.
        self.telemetry_clients: Dict[int, MachineTelemetryClient] = {}

        self.pipeline_frame_count = 0
        self.thread_lock = threading.Lock()
        self.detect_thread = None

    def start(self) -> None:
        """Execute the real-time face recognition pipeline loop."""
        logger.info("Initializing Employee Face Recognition HUD system...")

        # Load databases
        self.database = load_database(self.db_path)
        logger.info(f"Database contains {len(self.database)} enrolled employee record(s).")
        self.machine_database = load_machine_database(self.machines_db_path)
        logger.info(f"Machinery database contains {len(self.machine_database)} registered machine(s).")

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

                # Step 1: Always run tracking to maintain smooth 30 FPS display
                self.trk_count += 1
                t0 = time.perf_counter()
                self._run_tracking(frame)
                self.prof_trk.append((time.perf_counter() - t0) * 1000)

                # Step 2: Spawn background thread for heavy Detection/Recognition if needed
                self.pipeline_frame_count += 1
                if self.pipeline_frame_count % self.detect_interval == 0 or not self.tracked_faces:
                    if self.detect_thread is None or not self.detect_thread.is_alive():
                        self.det_count += 1
                        async_frame = frame.copy()
                        self.detect_thread = threading.Thread(target=self._run_detection_and_recognition, args=(async_frame,))
                        self.detect_thread.daemon = True
                        self.detect_thread.start()

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
                with self.thread_lock:
                    safe_faces = list(self.tracked_faces)
                    safe_machines = [dict(m) for m in self.tracked_machines]
                # Pull each machine's live telemetry fresh at render time from the
                # background poller's cache (no network call on this path -- the
                # poller thread owns that) so the card never shows baked-in stale data.
                for m in safe_machines:
                    client = self.telemetry_clients.get(m.get("marker_id"))
                    if client is not None:
                        m["telemetry"] = client.get_latest_state()
                        m["connected"] = client.is_connected()
                    else:
                        m["telemetry"] = None
                        m["connected"] = False
                output_frame = draw_overlay(frame, safe_faces, safe_machines, fps=fps)
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
        """Execute face detection and embedding recognition asynchronously."""
        t0 = time.perf_counter()
        detections = self.detector.detect(frame)
        if detections:
            detections = sorted(detections, key=lambda d: d.w * d.h, reverse=True)[:self.max_faces]
        self.prof_det.append((time.perf_counter() - t0) * 1000)

        with self.thread_lock:
            current_tracked_faces = list(self.tracked_faces)

        if not detections:
            with self.thread_lock:
                self.tracked_faces = []
                self.trackers = []
            new_tracked_faces: List[Dict[str, Any]] = []
        else:
            new_tracked_faces = self._detect_and_recognize_faces(detections, frame, current_tracked_faces)

        # Machine/PLC marker detection runs regardless of whether any faces were
        # found this cycle -- a machine with nobody standing near it must still
        # show its telemetry.
        self._detect_and_track_machines(frame, new_tracked_faces)

    def _detect_and_recognize_faces(
        self,
        detections: List[Any],
        frame: np.ndarray,
        current_tracked_faces: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process detected faces: IoU-cache/re-verify/extract, track, and publish incrementally.

        Returns the list of face entries built this cycle (used by the caller to determine
        which recognized employee, if any, to attribute as a machine's operator).
        """
        new_tracked_faces: List[Dict[str, Any]] = []
        new_trackers: List[Any] = []
        img_h, img_w = frame.shape[:2]
        for face_det in detections:
            x, y, w, h, score = face_det
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(img_w, x + w), min(img_h, y + h)
            new_box = (x1, y1, x2 - x1, y2 - y1)

            match_info = None
            if x2 > x1 and y2 > y1:
                # OPTIMIZATION: Check IoU against currently tracked faces
                best_iou = 0.0
                best_old_face = None
                for old_face in current_tracked_faces:
                    iou = calculate_iou(new_box, old_face["bbox"])
                    if iou > best_iou:
                        best_iou = iou
                        best_old_face = old_face
                
                # If the face hasn't moved much (IoU > 0.4), check if it needs re-verification
                if best_iou > 0.4 and best_old_face is not None:
                    time_since_verify = time.time() - best_old_face.get("last_verify", 0)
                    if time_since_verify < 2.5:
                        match_info = best_old_face["match"]
                        last_verify = best_old_face.get("last_verify", time.time())
                    else:
                        t_rec = time.perf_counter()
                        embedding = self.recognizer.extract_embedding(frame, face_det)
                        match_info = match_face(embedding, self.database, threshold=self.similarity_threshold)
                        self.prof_rec.append((time.perf_counter() - t_rec) * 1000)
                        last_verify = time.time()
                else:
                    t_rec = time.perf_counter()
                    embedding = self.recognizer.extract_embedding(frame, face_det)
                    match_info = match_face(embedding, self.database, threshold=self.similarity_threshold)
                    self.prof_rec.append((time.perf_counter() - t_rec) * 1000)
                    last_verify = time.time()
            else:
                last_verify = time.time()

            tracked_entry = {"bbox": new_box, "match": match_info, "last_verify": last_verify}

            tracker = create_opencv_tracker()
            if tracker is not None:
                try:
                    tracker.init(frame, new_box)
                    new_trackers.append(tracker)
                except Exception:
                    new_trackers.append(None)
            else:
                new_trackers.append(None)
            new_tracked_faces.append(tracked_entry)

            # Publish incrementally: a face appears on the HUD as soon as its
            # own recognition finishes, instead of waiting for every face
            # detected this cycle to finish first. Previously this was a
            # single publish after the whole loop, so e.g. 3 simultaneous
            # new faces (each ~250ms of SFace extraction) held up display of
            # ALL of them for ~750ms instead of showing the first one at
            # ~250ms.
            with self.thread_lock:
                self.tracked_faces = list(new_tracked_faces)
                self.trackers = list(new_trackers)

        return new_tracked_faces

    def _detect_and_track_machines(self, frame: np.ndarray, current_faces: List[Dict[str, Any]]) -> None:
        """Detect ArUco-tagged machines in the frame, start/reuse a telemetry poller for each,
        and attribute the current best-known recognized employee (if any) as the operator.

        Args:
            frame: The same frame face detection just ran on -- reused here, no extra capture.
            current_faces: Face entries built this cycle (from `_detect_and_recognize_faces`,
                or the previous cycle's cached faces if no new detections ran), used to pick
                an operator name for any machine detected here.
        """
        markers = self.machine_detector.detect(frame)

        if not markers:
            with self.thread_lock:
                self.tracked_machines = []
                self.machine_trackers = []
            return

        operator_name: Optional[str] = None
        for face_entry in current_faces:
            match = face_entry.get("match")
            if match:
                operator_name = match.get("name")
                break

        new_tracked_machines: List[Dict[str, Any]] = []
        new_machine_trackers: List[Any] = []

        for marker in markers:
            machine_record = match_machine(marker.marker_id, self.machine_database)
            if machine_record is None:
                continue  # unregistered marker ID -- ignore

            marker_bbox = marker.bbox
            tracked_entry = {
                "bbox": marker_bbox,
                "marker_id": marker.marker_id,
                "name": machine_record.get("name", "Unknown Machine"),
                "operator_name": operator_name,
            }

            if marker.marker_id not in self.telemetry_clients:
                client = MachineTelemetryClient(machine_record["api_base_url"])
                client.start()
                self.telemetry_clients[marker.marker_id] = client

            tracker = create_opencv_tracker()
            if tracker is not None:
                try:
                    tracker.init(frame, marker_bbox)
                    new_machine_trackers.append(tracker)
                except Exception:
                    new_machine_trackers.append(None)
            else:
                new_machine_trackers.append(None)
            new_tracked_machines.append(tracked_entry)

            # Publish incrementally, same reasoning as faces: don't make every
            # tagged machine wait for the slowest one in this cycle.
            with self.thread_lock:
                self.tracked_machines = list(new_tracked_machines)
                self.machine_trackers = list(new_machine_trackers)

    def _run_tracking(self, frame: np.ndarray) -> None:
        updated_faces = []
        updated_trackers = []
        with self.thread_lock:
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

            updated_machines = []
            updated_machine_trackers = []
            for i, tracker in enumerate(self.machine_trackers):
                machine_data = self.tracked_machines[i]
                if tracker is not None:
                    try:
                        success, box = tracker.update(frame)
                        if success:
                            x, y, w, h = [int(v) for v in box]
                            machine_data["bbox"] = (x, y, w, h)
                            updated_machines.append(machine_data)
                            updated_machine_trackers.append(tracker)
                        else:
                            logger.debug(f"Tracker update FAILED for machine at frame {self.pipeline_frame_count}")
                    except Exception as e:
                        logger.debug(f"Machine tracker update error: {e}")
            self.tracked_machines = updated_machines
            self.machine_trackers = updated_machine_trackers

    def cleanup(self) -> None:
        """Release hardware capture and display resources cleanly."""
        logger.info("Cleaning up pipeline hardware resources...")
        self.cap.release()
        if self.display is not None:
            self.display.close()
        for client in self.telemetry_clients.values():
            client.stop()
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
        "--machines-db", type=str, default="machinery/database/machines.json",
        help="Path to machine/PLC JSON database file (ArUco marker registry)"
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
    parser.add_argument(
        "--width", type=int, default=640,
        help="Camera capture width (increase to 1280 for far-away faces)"
    )
    parser.add_argument(
        "--height", type=int, default=480,
        help="Camera capture height (increase to 720 for far-away faces)"
    )

    args = parser.parse_args()

    pipeline = PipelineManager(
        camera_index=args.camera,
        db_path=args.db,
        machines_db_path=args.machines_db,
        detect_interval=args.detect_interval,
        similarity_threshold=args.threshold,
        max_faces=args.max_faces,
        no_display=args.no_display,
        width=args.width,
        height=args.height
    )
    pipeline.start()


if __name__ == "__main__":
    main()
