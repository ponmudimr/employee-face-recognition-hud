"""Force-injects a fake machine detection to show the dashboard card on the physical
display without needing a real ArUco marker to be detected.

Useful as a backup/demo tool (e.g. for a presentation) when live marker detection isn't
available or working, and for isolating "is the rendering code correct" from "is the
camera actually detecting the physical marker" while troubleshooting.

Must be run with the main HUD service stopped first (the camera only supports one
client at a time):

    sudo systemctl stop helmet-recognition.service
    python3 tools/demo_dashboard.py [duration_seconds]
    sudo systemctl start helmet-recognition.service
"""

import os
import sys
import time
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from capture import WebcamCapture, DisplayWindow
from overlay import draw_overlay

DEFAULT_DURATION_S = 30.0

FAKE_MACHINE = {
    "bbox": (220, 140, 200, 200),
    "marker_id": 0,
    "name": "Bottle Filling Line 1",
    "machine_id": "MCH-001",
    "operator_name": "Dinesh",
    "production_pct": 87.0,
    "parts": [
        {"name": "Sample Part A", "life_pct": 80, "needs_change": False},
        {"name": "Sample Part B", "life_pct": 15, "needs_change": True}
    ],
    "next_maintenance_due": "2026-09-20",
    "fault_reason": "TBD",
    "telemetry": {"status": "RUNNING", "running_hours": 128.7, "stopped_hours": 12.3},
    "connected": True
}


def main() -> None:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DURATION_S

    cap = WebcamCapture(device_index=-1, width=640, height=480)
    if not cap.open():
        print("Camera failed to open. Is helmet-recognition.service still running?")
        sys.exit(1)

    display = DisplayWindow(fullscreen=True)
    display.create()

    print(f"Showing demo dashboard for {duration:.0f}s. Press 'q' to stop early.")
    start = time.time()
    try:
        while time.time() - start < duration:
            ret, frame = cap.read()
            if ret and frame is not None:
                output = draw_overlay(frame, [], [FAKE_MACHINE], fps=30.0)
                display.show(output)
                key = display.poll_key(delay_ms=1)
                if key == ord('q') or key == 27:
                    break
            time.sleep(0.03)
    finally:
        display.close()
        cap.release()
        print("Demo done.")


if __name__ == "__main__":
    main()
