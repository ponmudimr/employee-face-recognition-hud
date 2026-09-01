"""CLI Enrollment Tool: Captures photos of a new employee via webcam, extracts embeddings, and appends to local JSON database."""

import argparse
import json
import logging
import os
import sys
import time
from typing import List, Dict, Any, Optional
import cv2
import numpy as np

# Add src to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from capture import WebcamCapture, DisplayWindow
from detect import FaceDetector
from recognize import FaceRecognizer

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("HUD-Enroll")


def save_employee_record(
    db_path: str,
    emp_id: str,
    name: str,
    role: str,
    embedding: np.ndarray
) -> bool:
    """Save or update employee record in the local JSON database file.

    Args:
        db_path: Path to database JSON file.
        emp_id: Employee unique identifier.
        name: Full name of employee.
        role: Employee role/title.
        embedding: Calculated average face embedding vector.

    Returns:
        bool: True if saved successfully.
    """
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    database: List[Dict[str, Any]] = []

    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    database = data
        except Exception as e:
            logger.warning(f"Could not parse existing DB file at {db_path}: {e}. Creating new database.")

    # Convert numpy embedding vector to serializable list
    emb_list = embedding.astype(float).tolist()

    new_record = {
        "id": emp_id,
        "name": name,
        "role": role,
        "embedding": emb_list,
        "enrolled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    # Update if ID already exists, otherwise append
    updated = False
    for i, rec in enumerate(database):
        if str(rec.get("id")) == str(emp_id):
            database[i] = new_record
            updated = True
            logger.info(f"Updated existing record for Employee ID: {emp_id}")
            break

    if not updated:
        database.append(new_record)
        logger.info(f"Added new record for Employee ID: {emp_id}")

    try:
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(database, f, indent=2)
        logger.info(f"Successfully saved employee database to '{db_path}'. Total enrolled: {len(database)}.")
        return True
    except Exception as e:
        logger.error(f"Failed to write database file '{db_path}': {e}")
        return False


def enroll_employee(
    emp_id: str,
    name: str,
    role: str,
    num_samples: int = 5,
    camera_index: int = 0,
    db_path: str = "enrollment/database/employees.json"
) -> None:
    """Capture face samples from webcam, extract embeddings, and save to employee database.

    Args:
        emp_id: Employee ID string.
        name: Employee full name.
        role: Employee role.
        num_samples: Number of facial image samples to capture.
        camera_index: V4L2 device index for webcam.
        db_path: Filepath for output JSON database.
    """
    logger.info(f"Starting face enrollment for '{name}' (ID: {emp_id}, Role: {role})...")
    logger.info(f"Target sample count: {num_samples}")

    cap = WebcamCapture(device_index=camera_index)
    if not cap.open():
        logger.error(f"Cannot open camera /dev/video{camera_index} for enrollment.")
        sys.exit(1)

    display = DisplayWindow(window_name="Employee Enrollment HUD", fullscreen=False)
    display.create()

    detector = FaceDetector()
    recognizer = FaceRecognizer()

    embeddings: List[np.ndarray] = []
    captured_count = 0

    logger.info("Position face in front of camera. Press SPACE to capture a photo sample, or 'q' to cancel.")

    try:
        while captured_count < num_samples:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.1)
                continue

            display_frame = frame.copy()
            detections = detector.detect(frame)

            # Draw prompt overlay
            cv2.putText(
                display_frame,
                f"Enrolling: {name} ({captured_count}/{num_samples} samples)",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )
            cv2.putText(
                display_frame,
                "Press SPACE to capture, 'q' to quit",
                (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

            # Draw detection boxes if present
            for (x, y, w, h, score) in detections:
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), (255, 255, 0), 2)

            display.show(display_frame)
            key = display.poll_key(delay_ms=30)

            if key == ord('q') or key == 27:
                logger.warning("Enrollment cancelled by user.")
                break
            elif key == 32:  # SPACE bar pressed to trigger capture
                img_h, img_w = frame.shape[:2]
                if detections:
                    x, y, w, h, _ = detections[0]
                    x1, y1 = max(0, x), max(0, y)
                    x2, y2 = min(img_w, x + w), min(img_h, y + h)
                    face_crop = frame[y1:y2, x1:x2]
                else:
                    # Fallback: center crop if detector is stubbed or no face detected
                    cx, cy = img_w // 2, img_h // 2
                    rw, rh = int(img_w * 0.4), int(img_h * 0.4)
                    face_crop = frame[max(0, cy - rh):min(img_h, cy + rh), max(0, cx - rw):min(img_w, cx + rw)]

                if detections:
                    emb = recognizer.extract_embedding(frame, detections[0])
                    embeddings.append(emb)
                    captured_count += 1
                    logger.info(f"Captured sample {captured_count}/{num_samples}.")
                    # Visual feedback flash
                    cv2.rectangle(display_frame, (0, 0), (img_w, img_h), (0, 255, 0), 10)
                    display.show(display_frame)
                    cv2.waitKey(200)
                elif face_crop.size > 0:
                    emb = recognizer.extract_embedding(face_crop)
                    embeddings.append(emb)
                    captured_count += 1
                    logger.info(f"Captured sample {captured_count}/{num_samples}.")
                    # Visual feedback flash
                    cv2.rectangle(display_frame, (0, 0), (img_w, img_h), (0, 255, 0), 10)
                    display.show(display_frame)
                    cv2.waitKey(200)

        if embeddings:
            # Calculate mean embedding vector across captured samples
            avg_embedding = np.mean(np.array(embeddings), axis=0)
            norm = np.linalg.norm(avg_embedding)
            if norm > 0:
                avg_embedding = avg_embedding / norm

            save_employee_record(db_path, emp_id, name, role, avg_embedding)
            logger.info("Enrollment completed successfully!")
        else:
            logger.error("No facial samples were captured. Enrollment aborted.")

    finally:
        cap.release()
        display.close()


def main() -> None:
    """CLI entrypoint for employee enrollment."""
    parser = argparse.ArgumentParser(description="Enroll employee faces into local HUD database")
    parser.add_argument("--id", type=str, help="Employee ID (e.g. EMP-101)")
    parser.add_argument("--name", type=str, help="Employee Full Name")
    parser.add_argument("--role", type=str, help="Employee Role / Job Title")
    parser.add_argument("--samples", type=int, default=5, help="Number of photo samples to capture (default: 5)")
    parser.add_argument("--camera", type=int, default=-1, help="Camera device index (-1 for OAK-D-Lite primary default, >=0 for V4L2 webcam)")
    parser.add_argument("--db", type=str, default="enrollment/database/employees.json", help="Database file output path")

    args = parser.parse_args()

    emp_id = args.id or input("Enter Employee ID: ").strip()
    name = args.name or input("Enter Employee Full Name: ").strip()
    role = args.role or input("Enter Employee Role: ").strip()

    if not emp_id or not name:
        logger.error("Employee ID and Name are required fields.")
        sys.exit(1)

    enroll_employee(
        emp_id=emp_id,
        name=name,
        role=role,
        num_samples=args.samples,
        camera_index=args.camera,
        db_path=args.db
    )


if __name__ == "__main__":
    main()
