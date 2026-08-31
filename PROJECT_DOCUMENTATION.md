# Employee Face Recognition AR HUD — Project Documentation & Engineering Log

## 1. Executive Summary
This document records all bring-up steps, architectural decisions, bug fixes, hardware integrations, and CLI usage instructions performed for the **Employee Face Recognition AR HUD** system deployed on the **Arduino UNO Q** board (Qualcomm Dragonwing QRB2210 ARM64 quad-core platform running Debian Linux) connected to an **HDMI / USB-C AR Glass display**.

---

## 2. System Architecture & Environment
- **Host Laptop:** Fedora Linux (`mrponmudi@fedora`), running Antigravity CLI (`agy`).
- **Target Hardware Board:** Arduino UNO Q / Qualcomm Dragonwing QRB2210 (`arduino@meryl`), IP: `10.10.148.191`.
- **Target OS:** Debian GNU/Linux 64-bit (`aarch64`).
- **Display Output:** HDMI / AR Glass display running Xfce desktop environment on `DISPLAY=:0`.
- **Primary Repository Location:** `/home/arduino/employee-face-recognition-hud` (Board) & `/home/mrponmudi/GIT/employee-face-recognition-hud` (Host).

---

## 3. Key Accomplishments & Technical Fixes

### 3.1 Python Environment & Native Debian Dependencies
- **Issue:** Standard `pip` was not initially installed on the Debian board.
- **Solution:** Configured native Debian arm64 packages via `apt` for zero-compilation deployment:
  ```bash
  sudo apt update && sudo apt install -y python3-pip python3-opencv python3-numpy python3-onnxruntime
  ```

### 3.2 Dual Camera Engine Integration (`src/capture.py`)
1. **Luxonis OAK-D-Lite (Intel Movidius MyriadX `03e7:2485`)**:
   - Installed Luxonis DepthAI library (`pip install depthai --break-system-packages`).
   - Installed USB permissions rule for non-root USB access:
     ```bash
     echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' | sudo tee /etc/udev/rules.d/80-movidius.rules
     sudo udevadm control --reload-rules && sudo udevadm trigger
     ```
   - Built `DepthAICapture` class compatible with DepthAI 3.9+ (`dai.node.ColorCamera`, `device.startPipeline()`, `device.getOutputQueue(cam.preview)`).
   - Prevented duplicate XLink device connection locks (`X_LINK_DEVICE_ALREADY_IN_USE`).

2. **Standard 1080p USB Webcams (`/dev/video2`, `/dev/video0`)**:
   - Bypassed broken GStreamer pipeline errors by explicitly forcing `cv2.CAP_V4L2` driver backend.
   - Implemented automatic `MJPEG` / `YUYV` FOURCC pixel format fallback and warmup frame verification for high-res 1080p cameras.

### 3.3 YuNet Face Detection Optimization (`src/detect.py`)
- **Fix:** Resolved missing `Tuple` typing import bug in `src/recognize.py`.
- **Sensitivity Optimization:** Lowered `confidence_threshold` from `0.60` to `0.45` to catch faces under normal ambient lighting.
- **Resolution Tuning:** Increased internal detection resolution from `320x240` to `640x480` so faces further away are detected clearly.
- **FPS Tuning:** Reduced `detect_interval` from 10 frames to 3 frames for 3x faster detection responsiveness.

### 3.4 Face Recognition & Embedding Engine (`src/recognize.py`)
- **Detection Model:** OpenCV YuNet ONNX model (`models/face_detection_yunet.onnx`).
- **Embedding Model:** OpenCV SFace ONNX model (`models/face_recognition_sface.onnx`).
- **Matching Metric:** 128-dimensional normalized embedding vectors compared via Cosine Similarity (`DEFAULT_MATCH_THRESHOLD = 0.363`).

---

## 4. How to Use the System

### 4.1 Check Connected Camera Devices
To list all available camera devices on the board:
```bash
v4l2-ctl --list-devices
```

### 4.2 Enroll an Employee Face
To capture photo samples of a new employee and register them in `enrollment/database/employees.json`:

```bash
# Using 1080p USB Webcam (Camera index 2)
python3 enrollment/enroll.py --camera 2 --id EMP-101 --name "Jane Doe" --role "Supervisor" --samples 5
```
*(Press **SPACEBAR** 5 times in front of the camera to capture facial samples).*

### 4.3 Run the Real-Time Face Recognition HUD

#### Option A: Running with Standard 1080p USB Webcam
```bash
export DISPLAY=:0
python3 src/main.py --camera 2
```

#### Option B: Running with Luxonis OAK-D-Lite Camera
```bash
export DISPLAY=:0
python3 src/main.py --camera -1
```

---

## 5. Automated Systemd Boot Service
To make the Face Recognition HUD autostart automatically whenever the Arduino board powers on:

```bash
sudo cp systemd/helmet-recognition.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable helmet-recognition.service
sudo systemctl start helmet-recognition.service
```

---

## 6. Verification & Test Suite
All 21 unit tests pass cleanly:
```bash
pytest tests/
```

*Documentation created on August 31, 2026 for the Employee Face Recognition HUD project.*
