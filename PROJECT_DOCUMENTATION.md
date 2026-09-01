# Employee Face Recognition AR HUD — Comprehensive Project Documentation & Engineering Log

---

## 1. Project Mission & Core Purpose ("Motto")
The core objective of this project is to build an **edge-computed, real-time Employee Face Recognition AR Head-Up Display (HUD)** system designed for wearable AR glasses or dedicated HDMI monitors attached to an **Arduino UNO Q board** (Qualcomm Dragonwing QRB2210 quad-core ARM Cortex-A53 platform running 64-bit Debian Linux).

The system performs real-time face detection, 128-dimensional embedding extraction, employee database matching, object tracking, and high-tech AR HUD graphic overlay rendering on `DISPLAY=:0` with ultra-low latency.

---

## 2. Hardware & Environment Specifications
- **Host Laptop:** Fedora Linux (`mrponmudi@fedora`), running Google Antigravity CLI (`agy`).
- **Target Embedded Board:** Arduino UNO Q / Qualcomm Dragonwing QRB2210 (`arduino@meryl`), IP: `10.10.148.191`, password `meryl`.
- **Target OS:** Debian GNU/Linux 64-bit ARM (`aarch64`).
- **Display Output Environment:** `DISPLAY=:0` (HDMI output rendering borderless fullscreen Xfce window).
- **Supported Cameras:**
  - **Standard USB 1080p Webcams** (`/dev/video2`, `/dev/video0`).
  - **Luxonis OAK-D-Lite Camera** (Intel Movidius MyriadX `03e7:2485`).

---

## 3. Comprehensive Debugging & Troubleshooting Log

Below is the complete record of every technical challenge, root cause, exact error message, and resolution implemented during project bring-up:

### 🐛 Bug #1: Missing `pip` command on board
- **Symptom:** `-bash: pip: command not found` when attempting `pip install -r requirements.txt`.
- **Root Cause:** Standard Python pip was not pre-installed on the Debian minimal image.
- **Resolution:** Installed native arm64 precompiled Debian packages directly via `apt` to avoid compilation overhead on ARM Cortex-A53:
  ```bash
  sudo apt update && sudo apt install -y python3-pip python3-opencv python3-numpy python3-onnxruntime
  ```

---

### 🐛 Bug #2: SSL certificate error on `git clone` & `git pull`
- **Symptom:** `fatal: unable to access ... certificate has expired (CAfile: /etc/ssl/certs/ca-certificates.crt)`
- **Root Cause:** Board system clock / CA certificate bundle misconfiguration during HTTPS git operations behind network portal.
- **Resolution:** Instructed git commands to bypass SSL verification:
  ```bash
  GIT_SSL_NO_VERIFY=true git clone https://github.com/ponmudimr/employee-face-recognition-hud.git
  GIT_SSL_NO_VERIFY=true git pull
  ```

---

### 🐛 Bug #3: Python Typing Import `NameError` in `src/recognize.py`
- **Symptom:**
  ```text
  File "/home/arduino/employee-face-recognition-hud/src/recognize.py", line 248, in FaceRecognizer
      def match(self, emb1: np.ndarray, emb2: np.ndarray) -> Tuple[float, bool]:
  NameError: name 'Tuple' is not defined. Did you mean: 'tuple'?
  ```
- **Root Cause:** Line 8 in `src/recognize.py` imported `List, Dict, Any, Optional` but omitted `Tuple`.
- **Resolution:** Updated line 8 of `src/recognize.py`:
  ```python
  from typing import List, Dict, Any, Optional, Tuple
  ```

---

### 🐛 Bug #4: Internal Qualcomm Venus Hardware Nodes vs. USB Webcams
- **Symptom:** Opening `/dev/video0` produced errors: `Device '/dev/video0' is not a capture device` / `Camera index out of range`.
- **Root Cause:** On Qualcomm Dragonwing QRB2210, `/dev/video0` (encoder) and `/dev/video1` (decoder) are internal Qualcomm Venus video codec hardware nodes, NOT USB webcam inputs.
- **Resolution:** Ran device scanning (`v4l2-ctl --list-devices`). Identified that external USB webcams get assigned to higher indices like `/dev/video2`.

---

### 🐛 Bug #5: Luxonis OAK-D-Lite USB Permission Denied
- **Symptom:**
  ```text
  [depthai] [warning] Insufficient permissions to communicate with X_LINK_UNBOOTED device with name "1.1.3". Make sure udev rules are set
  RuntimeError: No available devices
  ```
- **Root Cause:** Non-root user `arduino` lacked raw USB write permissions to the Intel Movidius MyriadX chip (`03e7:2485`).
- **Resolution:** Added Luxonis udev rule to `/etc/udev/rules.d/80-movidius.rules`:
  ```bash
  echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' | sudo tee /etc/udev/rules.d/80-movidius.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```

---

### 🐛 Bug #6: DepthAI 3.9+ Deprecated Node Syntax (`XLinkOut`)
- **Symptom:** `capture: Failed to open OAK-D-Lite camera via DepthAI: module 'depthai.node' has no attribute 'XLinkOut'`
- **Root Cause:** In `depthai` 3.9.0+, Luxonis deprecated `dai.node.XLinkOut` node creation in favor of direct queue binding on camera streams.
- **Resolution:** Updated `DepthAICapture.open()` in `src/capture.py` to use direct queue binding (`self.device.getOutputQueue(cam_rgb.preview, maxSize=4, blocking=False)`).

---

### 🐛 Bug #7: DepthAI 3.9+ `Device` Constructor Change
- **Symptom:**
  ```text
  Failed to open OAK-D-Lite camera via DepthAI: __init__(): incompatible constructor arguments.
  Invoked with: <depthai.Pipeline object at ...>
  ```
- **Root Cause:** DepthAI 3.9 changed `dai.Device(pipeline)` to `dai.Device()` with `device.startPipeline(pipeline)`.
- **Resolution:** Implemented dual-constructor fallback in `src/capture.py`:
  ```python
  try:
      self.device = dai.Device(pipeline)
  except Exception:
      self.device = dai.Device()
      self.device.startPipeline(pipeline)
  ```

---

### 🐛 Bug #8: Camera USB Device Lock (`X_LINK_DEVICE_ALREADY_IN_USE`)
- **Symptom:** `Cannot connect to device with name "1.1.3", it is used by another process. Error: X_LINK_DEVICE_ALREADY_IN_USE`
- **Root Cause:** Leftover python test processes held the MyriadX USB endpoint, and `WebcamCapture` was retrying `DepthAICapture` without closing failed instances.
- **Resolution:**
  1. Added explicit `oak_cap.release()` on failure in `src/capture.py`.
  2. Provided process kill and USB reset commands:
     ```bash
     pkill -9 -f python3
     echo '1-1.3' | sudo tee /sys/bus/usb/drivers/usb/unbind && sleep 2 && echo '1-1.3' | sudo tee /sys/bus/usb/drivers/usb/bind
     ```

---

### 🐛 Bug #9: OpenCV GStreamer Stream Error on 1080p USB Webcams
- **Symptom:**
  ```text
  [ WARN:0 ] global cap_gstreamer.cpp: Embedded video playback halted; module v4l2src0 reported: Internal data stream error.
  [WARNING] capture: Attempted frame read on unopened camera stream.
  ```
- **Root Cause:** OpenCV defaulted to GStreamer backend on Debian, failing pixel format negotiation on 1080p UVC webcams (`/dev/video2`).
- **Resolution:** Updated `WebcamCapture` in `src/capture.py` to:
  1. Force `cv2.CAP_V4L2` driver backend (`cv2.VideoCapture(self.device_index, cv2.CAP_V4L2)`).
  2. Negotiate `MJPEG` and `YUYV` FOURCC pixel formats (`cv2.VideoWriter_fourcc(*'MJPG')`).
  3. Perform a 5-frame warmup read to verify live stream stability before returning success.

---

### 🐛 Bug #10: Low Face Detection Sensitivity / Unresponsive Detection
- **Symptom:** Camera window opened, but faces were not being detected or highlighted.
- **Root Cause:**
  1. YuNet confidence threshold was too high (`0.60`).
  2. Frame downscaling size was too small (`320x240`), making distant faces too tiny to detect.
  3. Detection interval was running only once every 10 frames (`detect_interval=10`).
- **Resolution:**
  1. Lowered `confidence_threshold` to `0.45` in `src/detect.py`.
  2. Increased downscale resolution to `640x480` in `src/detect.py` for 4x higher detection detail.
  3. Decreased `detect_interval` to `3` frames in `src/main.py` for 3x faster response.

---

## 4. Complete CLI Command Reference

### 4.1 Check Video Devices
```bash
v4l2-ctl --list-devices
```

### 4.2 Enroll New Employee Face
```bash
# Enroll employee using 1080p webcam on /dev/video2
python3 enrollment/enroll.py --camera 2 --id EMP-101 --name "Jane Doe" --role "Engineer" --samples 5
```

### 4.3 Run Face Recognition HUD

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

### 4.4 Run System Test Suite
```bash
pytest tests/
```

---

## 5. Summary of Modified Project Files & Commit History
- `src/capture.py`: Primary camera capture manager (OAK-D-Lite-AF DepthAI default + continuous autofocus `setAutoFocusMode` + V4L2 MJPEG fallback + display window).
- `src/detect.py`: YuNet face detector wrapper (threshold `0.45`, resolution `640x480`).
- `src/recognize.py`: SFace face embedding extractor, cosine similarity matcher, fixed `Tuple` import.
- `src/main.py`: Real-time pipeline orchestrator linking capture (OAK-D-Lite default), detection (`interval=3`), recognition, landmark alignment, tracking, and HUD overlay.
- `enrollment/enroll.py`: Employee enrollment tool (defaults to OAK-D-Lite primary camera with 5-point landmark alignment).
- `requirements.txt`: Project dependencies including `depthai>=2.20.0`.
- `PERSUSGFILES/`: Hardware 3D CAD STEP files & Gerber PCB files for Arduino UNO Q enclosure (`ABX00162`).
- `PROJECT_DOCUMENTATION.md`: Exhaustive project documentation and engineering log.
- **Commit `1c0188e`**: Added capture, detect, recognize, main pipeline modules & CAD files to `origin/main`.
- **Commit `157d8ba`**: Fixed recognition threshold default (`0.363`) and enabled OpenCV SFace 5-point facial landmark alignment (`alignCrop`).
- **OAK-D-Lite-AF Primary Switch**: Configured Luxonis OAK-D-Lite-AF (model 4125A1) as the default primary camera (`--camera -1`) across `src/capture.py`, `src/main.py`, and `enrollment/enroll.py`, and added continuous video autofocus (`AutoFocusMode.CONTINUOUS_VIDEO`).
