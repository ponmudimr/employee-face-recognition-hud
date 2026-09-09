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

### 🐛 Bug #11: `NameError: name 'DEFAULT_MATCH_THRESHOLD' is not defined` in `src/main.py`
- **Symptom:** `src/main.py` failed on startup with `NameError: name 'DEFAULT_MATCH_THRESHOLD' is not defined` in `PipelineManager.__init__`.
- **Root Cause:** `DEFAULT_MATCH_THRESHOLD` is defined in `src/recognize.py` (`DEFAULT_MATCH_THRESHOLD = 0.363`), but was missing from the import line in `src/main.py`.
- **Resolution:** Added `DEFAULT_MATCH_THRESHOLD` to the `recognize` module import in `src/main.py`:
  ```python
  from recognize import FaceRecognizer, load_database, match_face, DEFAULT_MATCH_THRESHOLD
  ```

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
- **Commit `9c4e2ee`**: Switched primary camera default to Luxonis OAK-D-Lite-AF (`--camera -1`) and enabled continuous video autofocus (`AutoFocusMode.CONTINUOUS_VIDEO`).
- **Commit `06d53e8`**: Fixed `NameError: name 'DEFAULT_MATCH_THRESHOLD' is not defined` by importing `DEFAULT_MATCH_THRESHOLD` from `recognize` module into `src/main.py`.
- **Commit `c681cf8`**: Registered `atexit` and `signal` (`SIGINT`/`SIGTERM`) hardware release handlers in `src/main.py` to guarantee `device.close()` / `release()` runs on any exit or kill signal, preventing recurring `X_LINK_DEVICE_ALREADY_IN_USE` USB lockups. Verified live on board (31.7 FPS, clean shutdown).
- **Commit `292cd04`**: Reverted the winning-match log in `src/recognize.py` from `INFO` back to `DEBUG` (was bumped to `INFO` in `91b9354` for threshold debugging). Fixed `README.md` quick-start defaults to match `main.py`'s actual current values. Fixed `tests/test_recognize.py::test_default_threshold` to assert against the `DEFAULT_MATCH_THRESHOLD` constant instead of a hardcoded stale `0.363`.
- **Commit `f166ae3`**: Retargeted `systemd/helmet-recognition.service` from the dev laptop's user/paths to the actual Arduino UNO Q board (`user=arduino`, `--camera -1` for OAK-D-Lite). Changed `Restart=always` to `Restart=on-failure` so ESC/`q` on the HUD exits cleanly and stays stopped, while a camera-open failure or crash still auto-recovers. Added `systemd/setup_startc.sh`, which provisions a `startc` command to manually relaunch the HUD from a terminal.

### DepthAI V2 vs V3 Compatibility Fixes
- Addressed a critical `X_LINK_DEVICE_ALREADY_IN_USE` lockup error that occurred due to a V2 API mismatch with DepthAI `3.9.0`.
- Pinned `depthai>=2.20.0,<3.0.0.0` in `requirements.txt` to strictly enforce the V2 API, which correctly supports RVC2 hardware like the OAK-D-Lite-AF.
- Re-architected `DepthAICapture` pipeline instantiation to mirror stable implementations from legacy projects (using `createColorCamera()` instead of `create(dai.node.ColorCamera)`) to bypass unresolved firmware crashes in mixed V2 environments.
- Implemented robust shutdown hooks (`while self.q_rgb.has(): self.q_rgb.get()`) to thoroughly drain the `XLinkOut` message queue before executing `device.close()`. This successfully mitigates the MyriadX Watchdog `ErrorId 9001` hardware fault, which previously locked the camera requiring a manual physical USB power-cycle.

### Recognition & Detection Threshold Tuning
- Lowered the **YuNet Face Detector confidence threshold** from `0.45` to `0.35` in `src/main.py` and `enrollment/enroll.py`. This ensures faces are properly detected and tracked even in poor or varying lighting conditions.
- Lowered the **SFace Cosine Similarity match threshold** from `0.363` to `0.30` in `src/recognize.py`. This provides higher tolerance for angle variations and lighting changes when comparing live feeds against enrolled database embeddings, solving "UNKNOWN SUBJECT" false negatives.

### Hardware Acceleration (GPU OpenCL)
- Based on the Arduino UNO Q / Qualcomm Dragonwing QRB2210 Datasheet (Section 8.1 / 8.3), the integrated **Adreno 702 GPU** provides OpenCL 2.0 support via the Mesa driver stack.
- The `FaceDetectorYN` and `FaceRecognizerSF` instantiations in `src/detect.py` and `src/recognize.py` have been explicitly optimized to pass `cv2.dnn.DNN_BACKEND_OPENCV` and `cv2.dnn.DNN_TARGET_OPENCL`.
- This correctly offloads the compute-intensive neural network inference from the Cortex-A53 CPU to the Adreno 702 GPU, yielding a massive performance boost and lowering CPU thermals.

### Performance Note (September 2)
- Reverted the `DNN_TARGET_OPENCL` optimizations back to `DNN_TARGET_CPU`.
- On the Qualcomm Dragonwing QRB2210 running Debian, the OpenCV OpenCL backend incurs massive memory copy overhead between the CPU and GPU (lack of zero-copy buffers), causing the FPS to drop from 30 FPS to 1.6 FPS. The Cortex-A53 cores handle the YuNet model much faster natively.

### Performance Note (September 2 - Later)
- Discovered that scaling to multiple faces (`--max-faces 3`) caused severe micro-stuttering because SFace embedding math takes ~100ms per face (so 3 faces = ~300ms freeze per detection cycle).
- **Resolution:** Re-architected the main pipeline (`src/main.py`) to utilize **Asynchronous Threading**.
  - The heavy detection and recognition operations (YuNet + SFace) are now offloaded to a background daemon thread.
  - The main display loop exclusively runs the lightweight MOSSE tracker.
  - This fully decouples the camera display framerate from the AI compute time, eliminating the 300ms visual stutters entirely and maintaining a smooth 30 FPS display even with multiple people in frame.
  - Tracker was permanently swapped to `cv2.legacy.TrackerMOSSE_create()` as CSRT was too heavy (~100ms) on the Cortex-A53 without hardware acceleration.

### Threshold Customization
- **Strict Face Matching:** The default SFace Cosine Similarity match threshold in `src/recognize.py` was increased from the official OpenCV default of `0.363` to a very strict `0.60`.
- The system will now completely ignore faces and label them "UNKNOWN SUBJECT" unless they achieve at least a 60% raw similarity score to the enrolled database photo.

---

## 6. AR Helmet Deployment (systemd Auto-Start)

The target deployment is a wearable AR helmet/glasses driven by the Arduino UNO Q board (hostname `meryl`, SSH user `arduino`). The board runs the HUD as a systemd service so it comes up automatically on power-on with no manual login required.

### 6.1 How it works
- **Unit file:** `systemd/helmet-recognition.service`. Installed to `/etc/systemd/system/helmet-recognition.service` on the board, enabled via `WantedBy=graphical.target`.
- **Camera:** launches with `--camera -1` (OAK-D-Lite, the board's primary camera).
- **Display:** `DISPLAY=:0` / `XAUTHORITY=/home/arduino/.Xauthority`, targeting the board's `lightdm`-managed autologin X session on seat0.
- **`ExecStartPre=/bin/sleep 5`** gives the Xorg/lightdm session and OAK-D-Lite USB enumeration a moment to settle before the pipeline attaches. See gotcha in §9 — this is sometimes not quite long enough on a cold boot.
- **Restart policy — `Restart=on-failure`, `StartLimitIntervalSec=0`:** a clean exit (pressing **ESC** or `q` in the HUD window, which `src/main.py`'s display loop already treats as quit) exits with code 0 and the service **stays stopped**, freeing the board for other use. A camera-open failure or crash (non-zero exit) triggers an unlimited retry every `RestartSec=5s` — important since this is an unattended headset with no way to manually restart it if it silently gave up after N failed attempts.

### 6.2 Manual start: `startc`
- `systemd/setup_startc.sh` provisions `/usr/local/bin/startc` on the board — run `startc` from any terminal to relaunch the HUD after a clean ESC/`q` exit.
- Backed by `/etc/sudoers.d/helmet-recognition`, a passwordless-sudo rule scoped **only** to `systemctl start/stop/restart/status helmet-recognition.service` (not general root access), so `startc` doesn't prompt for a password.
- Re-run `sudo bash systemd/setup_startc.sh` on the board any time the unit file changes, to reinstall it and reload systemd.

### 6.3 Verified on-device (2026-09-09)
- Full power-cycle test: rebooted the board, systemd started the service automatically at boot with no manual intervention — proves the `enable` + `WantedBy=graphical.target` wiring.
- Self-healing: on that same cold boot, the first start attempt failed (`Cannot find any device with given deviceInfo` — OAK-D-Lite not yet enumerated), and `Restart=on-failure` retried 5s later successfully. See §9 for the underlying gotcha.
- Clean-exit behavior: simulated via `systemctl stop` (same code path as the app's own clean exit) — service went `inactive` and did not respawn, as intended. `startc` then relaunched it successfully with no password prompt.

---

## 7. Session Log — 2026-09-09

Continuing the bug/fix log from §3 above.

### 🐛 Bug #12: `pytest` INTERNALERROR from duplicate `test_detect.py`
- **Symptom:** Running bare `pytest` (not `pytest tests/`) crashed with `INTERNALERROR` instead of collecting/running tests.
- **Root Cause:** A stray, untracked `test_detect.py` at repo root (leftover from an earlier ad-hoc session) called `exit(1)` at import time when it couldn't open a camera, and additionally collided on module name with `tests/test_detect.py` (no `__init__.py` in either directory).
- **Resolution:** Deleted the stray root-level `test_detect.py`, along with 13 other untracked one-off `patch_*.py`/`fix_indent*.py` throwaway scripts from earlier sessions (their edits were already applied and committed — they were just clutter) and a stray `.README.md.swp` vim swapfile.

### 🐛 Bug #13: Stale test asserting hardcoded old threshold
- **Symptom:** After fixing Bug #12 and running the full suite, `tests/test_recognize.py::test_default_threshold` failed: `assert 0.6 == 0.363`.
- **Root Cause:** `DEFAULT_MATCH_THRESHOLD` was deliberately changed from `0.363` to `0.60` (commit `85926bd`), but this test still hardcoded the old value.
- **Resolution:** Changed the assertion to compare against the `DEFAULT_MATCH_THRESHOLD` constant instead of a literal, so it can't drift again.

### 🐛 Bug #14: systemd `Restart=always` fights a deliberate ESC exit
- **Symptom:** The AR-helmet systemd unit (originally written for the dev laptop, with wrong `User=`/paths and `--camera 0`) used `Restart=always`, so exiting the HUD via ESC/`q` to use the board for something else would just get relaunched 5 seconds later.
- **Root Cause:** `Restart=always` restarts on *any* exit, including a clean/intentional one (exit code 0) — no distinction from a crash.
- **Resolution:** Retargeted the unit to the board (`User=arduino`, `/home/arduino/employee-face-recognition-hud`, `--camera -1`), and changed to `Restart=on-failure` so only a non-zero exit (crash, camera failure) triggers auto-restart; a clean ESC/`q` exit stays stopped. Added the `startc` command (§6.2) to manually relaunch when desired.

### ℹ️ Infra note: Claude Code's Bash tool sandboxes LAN access by default
Not a bug in this repo, but cost significant time this session and will bite any future AI session working on this board over SSH: **Claude Code's Bash tool sandboxes network access by default**, and that sandbox appears to block direct connections to arbitrary private LAN IPs (like the board's `10.70.x.x` address) even when a human's own terminal on the same machine connects fine. Symptom looked exactly like "the board went offline" (connection timeouts, "no route to host") but was actually the tool's own sandbox. Fix: pass `dangerouslyDisableSandbox: true` on Bash calls that need to reach the board.

Separately, the actual SSH/network path to the board in this session was also genuinely flaky (independent of the sandbox issue) — commands would intermittently hang or timeout with no clear pattern tied to payload size. `scp` in particular reliably hung. Workarounds used successfully:
- Wrap SSH commands in a bounded retry loop (`for attempt in 1..N; do timeout ...; done`).
- For file transfers, avoid `scp`; pipe `base64`-encoded content through a single `ssh ... "echo '<b64>' | base64 -d > file"` command instead.

---

## 8. Current Status & Next Steps (as of 2026-09-09)

**Done:**
- Core pipeline (capture → YuNet detect → SFace recognize → MOSSE track → HUD overlay) working on both the dev laptop (built-in webcam) and the target board (OAK-D-Lite).
- Repo cleanup: stray scripts/files removed, `pytest` passes cleanly (21 tests), stale doc/test drift fixed.
- Board (`meryl`) has systemd auto-start installed, enabled, and verified across a full power cycle, including self-healing from a cold-boot camera race.
- ESC/`q` clean-exit behavior fixed to actually stay exited; `startc` command added for manual restart.
- Global (`~/.claude/`) config set: `includeCoAuthoredBy: false` + a strict CLAUDE.md rule — no AI attribution in any commit/PR from this project (or any project) going forward.
- 2 commits made locally (`292cd04`, `f166ae3`) — **not yet pushed to `origin/main`** as of this writing; ask the user before pushing.

**Known gaps / planned next (not yet done):**
- `ExecStartPre=/bin/sleep 5` in the systemd unit is sometimes too short for OAK-D-Lite USB enumeration on a cold boot, causing one failed start attempt before the retry succeeds (see §9). Bumping to ~10-15s would likely eliminate this; flagged to the user but not yet applied — confirm before changing.
- Physical verification that pressing ESC on the actual AR glass hardware exits cleanly hasn't been done (only the equivalent `systemctl stop` code path was verified remotely).
- Duplicate `"Cleaning up pipeline hardware resources..."` log lines appear on shutdown (both the `atexit` handler and the SIGTERM handler call `cleanup()`) — cosmetic only, not fixed.

---

## 9. Known Issues / Gotchas

- **Board IP changes on every reboot** (DHCP, no static lease configured) and `meryl.local` mDNS resolution did not work reliably in this session — after any board power-cycle, rediscover its current IP (have the user SSH in manually and report the address, or check the router's DHCP client list) rather than assuming the last-known IP still works.
- **Claude Code's Bash tool sandbox blocks direct connections to the board's LAN IP by default** — pass `dangerouslyDisableSandbox: true` for any Bash call that needs to reach it. Without this it looks exactly like the board is offline. See §7.
- **The SSH/network path to the board is flaky** — wrap remote commands in retry loops; avoid `scp` (prefer base64-over-ssh for file transfers). See §7.
- **Employee database is per-machine and gitignored** (`enrollment/database/*`, per `.gitignore`) — the dev laptop's local database is empty, while the board's has 5 enrolled employee records (independently enrolled there via `enrollment/enroll.py`). Don't assume the two are in sync.
- **A plaintext board SSH password already exists in §2 of this file** (Hardware & Environment, from an earlier session, alongside a since-stale IP). Do not add further live credentials to this or any tracked file going forward (see project `CLAUDE.md`) — if this repository is ever made public, rotate that board password first.
- **`--camera -1` (OAK-D-Lite) is the board's default and what the systemd service uses.** The dev laptop has no OAK-D-Lite attached; use `--camera 0` there (its built-in webcam) for local testing instead — don't copy laptop-tested camera args onto the board or vice versa.
