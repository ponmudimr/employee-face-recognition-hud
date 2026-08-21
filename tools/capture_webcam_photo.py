"""Utility script to capture a single photo from the local webcam after allowing auto-exposure to settle."""

import argparse
import os
import sys
import time
import cv2


def capture_photo(output_path: str, camera_index: int = 0, warmup_frames: int = 15) -> bool:
    """Open webcam, discard warmup frames, capture single frame, and save to output_path.

    Args:
        output_path: Destination image path (JPG/PNG).
        camera_index: V4L2 webcam index (default 0).
        warmup_frames: Number of initial frames to discard for auto-exposure.

    Returns:
        bool: True if photo was captured and saved successfully.
    """
    print(f"Opening camera /dev/video{camera_index}...")
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(
            f"ERROR: Webcam device /dev/video{camera_index} could not be opened. "
            "Ensure a USB webcam is connected and the user has permissions."
        )
        return False

    print(f"Discarding initial {warmup_frames} frames for camera auto-exposure settlement...")
    for i in range(warmup_frames):
        ret, frame = cap.read()
        if not ret:
            print(f"Warning: Failed reading warmup frame {i+1}/{warmup_frames}.")
        time.sleep(0.05)

    # Capture target frame
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        print("ERROR: Failed to capture photo frame from webcam.")
        return False

    # Ensure parent directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    success = cv2.imwrite(output_path, frame)
    if success:
        print(f"SUCCESS: Captured photo saved to '{output_path}' ({frame.shape[1]}x{frame.shape[0]} px).")
        return True
    else:
        print(f"ERROR: Failed to save captured photo to '{output_path}'.")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture a single photo from webcam")
    parser.add_argument("output_path", type=str, help="Output image file path (e.g. tests/fixtures/real_face1.jpg)")
    parser.add_argument("--camera", type=int, default=0, help="V4L2 camera device index (default: 0)")
    parser.add_argument("--warmup", type=int, default=15, help="Number of warmup frames to discard (default: 15)")

    args = parser.parse_args()

    success = capture_photo(args.output_path, camera_index=args.camera, warmup_frames=args.warmup)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
