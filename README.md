# Employee Face Recognition HUD

A lightweight, real-time face recognition and heads-up display (HUD) system optimized for edge platforms like the **Arduino UNO Q** (Qualcomm Dragonwing QRB2210 running Debian Linux). 

The system reads frames from a USB webcam, downscales them for fast neural network inference on quad-core ARM Cortex-A53 hardware, tracks faces using OpenCV object trackers, extracts face feature embeddings, matches them against a local employee database using cosine similarity, and renders a futuristic HUD overlay to an AR glass display via HDMI/USB-C.

---

## Hardware & Environment

- **Target Board:** Arduino UNO Q / Qualcomm Dragonwing QRB2210
- **Processor:** Quad-Core ARM Cortex-A53
- **Operating System:** Debian Linux
- **Camera Input:** USB Webcam (`/dev/video0`)
- **Display Output:** AR Glass Display over HDMI / USB-C (`DISPLAY=:0`)

---

## Key Features

- **Resource Efficient:** Specifically tailored for low-power ARM Cortex-A53 devices with limited RAM (2–4 GB), avoiding heavy dependencies like `dlib` or `face_recognition`.
- **Hybrid Detection & Tracking:** Runs face detection models every $N$ frames and utilizes OpenCV object tracking (KCF/CSRT) in intermediate frames to reduce CPU overhead.
- **HUD Graphic Overlay:** Renders corner reticles, semi-transparent employee metadata cards (Name, Role, ID, Match percentage), and real-time FPS metrics.
- **CLI Enrollment Tool:** Simple interactive command-line interface to capture facial photo samples and generate employee database records.
- **Machine/PLC Recognition:** Detects ArUco-marker-tagged industrial machines and overlays their live telemetry (phase, production count, operator) pulled from a machine's own backend (e.g. a BottleWise-style digital twin) — see [Machine Recognition](#machine-recognition) below.
- **Hardware Resilience:** Robust error handling for board bring-up stages when the webcam or display environment is not yet online.
- **Systemd Integration:** Includes a systemd service unit for autostarting the HUD pipeline on boot.

---

## Project Structure

```
employee-face-recognition-hud/
├── src/
│   ├── capture.py            # USB webcam VideoCapture wrapper & borderless AR HUD display manager
│   ├── detect.py             # Downscaled face detection wrapper (YuNet / Res10 SSD)
│   ├── recognize.py          # Face embedding extraction & cosine similarity matching
│   ├── machine_detect.py     # ArUco marker detection & machine database matching
│   ├── machine_telemetry.py  # Background poller for a machine's live telemetry backend
│   ├── overlay.py            # HUD reticles, employee/machine info cards, & FPS counter renderer
│   └── main.py                # Main pipeline orchestrator (capture -> detect -> recognize -> track -> overlay -> display)
├── enrollment/
│   ├── enroll.py          # Interactive CLI script for registering new employees
│   └── database/          # Directory storing the local employee JSON database (gitignored)
├── machinery/
│   ├── register_machine.py  # CLI script to assign an ArUco marker to a machine + generate its printable marker
│   ├── markers/              # Generated printable marker PNGs (gitignored)
│   └── database/             # Directory storing the local machine JSON database (gitignored)
├── models/                 # Model weights directory & ONNX model download guide
│   └── README.md          # Download instructions for YuNet & SFace ONNX models
├── systemd/
│   └── helmet-recognition.service   # Systemd autostart unit file for Debian Linux
├── tests/
│   └── test_recognize.py  # Pytest test suite for vector similarity and matching logic
├── requirements.txt        # Python package dependencies (opencv-python, onnxruntime, numpy, requests, pytest)
└── .gitignore               # Ignores model weights, database files, and python caches
```

---

## Getting Started

### 1. Prerequisites & Installation

Clone the repository and install the Python dependencies:

```bash
git clone git@github.com:ponmudimr/employee-face-recognition-hud.git
cd employee-face-recognition-hud
pip install -r requirements.txt
```

### 2. Model Setup

Download the recommended lightweight ONNX model weights into the `models/` directory (see [`models/README.md`](models/README.md) for details):

```bash
# Download YuNet Face Detector
wget -O models/face_detection_yunet.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx

# Download SFace Face Recognizer
wget -O models/face_recognition_sface.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
```

### 3. Enrolling Employees

Use the CLI enrollment script to register employee facial embeddings into the local database:

```bash
python3 enrollment/enroll.py --id EMP-101 --name "Jane Doe" --role "Site Supervisor" --samples 5
```

### 4. Running the HUD Pipeline

Launch the real-time HUD pipeline:

```bash
python3 src/main.py --camera 2 --detect-interval 3 --threshold 0.60
```

**Options:**
- `--camera`: V4L2 device index, or `-1` for the OAK-D-Lite primary default (default: `-1`).
- `--db`: Path to employee JSON database (default: `enrollment/database/employees.json`).
- `--detect-interval`: Frequency of running full face detection in frames (default: `3`).
- `--threshold`: Cosine similarity cutoff for recognition (default: `0.60`).
- `--max-faces`: Maximum number of largest faces to track simultaneously (default: `3`).
- `--width` / `--height`: Camera capture resolution (default: `640`x`480`).
- `--no-display`: Headless execution without rendering GUI window.

---

## Machine Recognition

The HUD can also identify tagged industrial machines/PLCs and overlay their live telemetry, alongside the existing face recognition. A machine is identified by a printed **ArUco marker** sticker (not a trained visual detector — see [`PROJECT_DOCUMENTATION.md`](PROJECT_DOCUMENTATION.md) for why), which is cheap to detect on this hardware and reliable at odd angles/distance.

### 1. Register a machine

```bash
python3 machinery/register_machine.py \
  --marker-id 0 \
  --name "Bottle Filling Line" \
  --api-url http://192.168.1.50:3001
```

`--api-url` is the base URL of the machine's own telemetry backend (must expose a `GET /api/state` REST endpoint — this matches a BottleWise Digital Twin backend out of the box). This saves the machine to `machinery/database/machines.json` and generates a printable marker image at `machinery/markers/marker_0.png` — print it and attach it to the machine's panel.

### 2. Run the HUD as usual

```bash
python3 src/main.py --camera -1 --machines-db machinery/database/machines.json
```

When the marker comes into view, the HUD polls that machine's `/api/state` on a background thread (never blocking the display loop) and shows a card with its current phase/progress, production count, and — if a recognized employee is also in frame — their name as the operator.

---

## Running Tests

Execute the unit tests using `pytest`:

```bash
pytest tests/
```

---

## Systemd Autostart Service

To configure the HUD pipeline to automatically start on boot on your Arduino UNO Q board:

```bash
# 1. Copy service file to systemd directory
sudo cp systemd/helmet-recognition.service /etc/systemd/system/

# 2. Reload systemd daemon
sudo systemctl daemon-reload

# 3. Enable and start the service
sudo systemctl enable helmet-recognition.service
sudo systemctl start helmet-recognition.service
```

---

## License

MIT License.
