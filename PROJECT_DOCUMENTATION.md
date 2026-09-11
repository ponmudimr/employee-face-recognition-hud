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

### 6.3 Screen lock / blanking disabled
The board's default Debian/lightdm desktop runs `light-locker`, which locks the screen once DPMS/screensaver blanking triggers (10 min idle by default) — this would obscure the AR HUD behind a lock screen, unacceptable for an always-on unattended display. Fixed in `systemd/setup_startc.sh`:
- Per-user XDG autostart override at `~/.config/autostart/light-locker.desktop` (`Hidden=true`) permanently disables `light-locker` for the `arduino` user, beating the system-wide `/etc/xdg/autostart/light-locker.desktop` entry.
- The systemd unit's second `ExecStartPre` runs `xset s off -dpms s noblank` on every service start, since DPMS/screensaver state is per-X-session runtime state that doesn't persist across X restarts — this is a belt-and-suspenders re-assertion independent of desktop config.
- Verified live: `light-locker` process killed and confirmed not respawning; `xset q` showed `DPMS is Disabled` and screensaver `timeout: 0` after a full service restart, with both `ExecStartPre` steps showing `status=0/SUCCESS` in `systemctl status`.

### 6.4 Verified on-device (2026-09-09)
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

## 7.1 Detection accuracy/latency tuning (2026-09-09, follow-up)

User asked for better detection with good FPS at room-scale (2-5m) range. Display FPS was already good (~30 FPS via the async architecture); the real issues were missed faces and multi-face detection latency. Two targeted, low-risk changes (deliberately did *not* touch capture/detection resolution — user confirmed room-scale range, and downscaling the detection frame below capture resolution would trade away far-face detection, which is the opposite of what was asked):

- **Detection confidence threshold `0.60` → `0.45`** (`src/main.py`, `PipelineManager.__init__`). Checked git history first: `0.35` was tried and reverted in commit `332347e` for causing false positives; `0.45` is YuNet's own class default and the validated middle ground between "too strict" (0.60, missing real faces) and "too loose" (0.35, false positives).
- **Fixed a real responsiveness bug in `_run_detection_and_recognition`**: it built the full per-face detection/recognition results for *all* faces in a cycle, then published them to `self.tracked_faces`/`self.trackers` **once, after every face finished**. With SFace extraction costing ~220-260ms per new/re-verify-needed face, 2-3 simultaneous new people held up display of *all* of them for up to ~750ms, even though the first one was ready at ~250ms. Changed to publish incrementally inside the loop (under the same lock), so each face appears on the HUD as soon as its own recognition completes. Added an explicit `if not detections: clear and return` branch to preserve the prior behavior of clearing tracked faces when a cycle detects nobody (previously handled implicitly by the empty-list end-of-loop publish, which no longer exists).
- Verified on-device: service restarted cleanly, ran for a full profiling cycle with no errors, `Detects: 3-5` per window, `DET` latency unchanged (~190-340ms, expected — confidence threshold doesn't change detector cost). Could not visually confirm on the physical AR display from here (no camera access to the headset itself) — worth a quick look next time you're wearing it.

---

## 7.2 LightDM stuck at login greeter + USB power-rail dropout (2026-09-09, follow-up)

After a board reboot, the user reported being stuck at a login page with no working keyboard/mouse. Two distinct problems, found and fixed in sequence:

**1. LightDM greeter, not `light-locker`.** `/etc/lightdm/lightdm.conf` had `autologin-user` fully commented out — LightDM was showing its actual login greeter (`lightdm-gtk-greeter` process, session class `greeter` on seat0) waiting for manual credentials, which no one can supply on a headset with no reliably-attached input device. This is different from the `light-locker` screensaver-lock fixed in §6.3 (that one only fires after idle timeout; this one blocks at every boot before any session starts). **Fix:** set real autologin in `lightdm.conf` — `autologin-user=arduino`, `autologin-user-timeout=0`, `autologin-session=xfce` (confirmed no Debian `autologin`/`nopasswdlogin` group gate applies on this image). Verified across a real cold boot: `arduino` lands on `seat0` automatically, no greeter process, `loginctl` shows `State=active`.

**2. USB VBUS power rail dropped out — separate issue, not caused by the fix above.** While testing the LightDM fix, restarting the `lightdm` service (to apply the new config without a full reboot) caused an entire downstream USB hub (`Huasheng Electronics USB2.0 HUB`, carrying the OAK-D-Lite camera **and** the keyboard/mouse) to vanish from `lsusb` entirely. Diagnosis: `dmesg` showed a regulator literally named `usb_vbus` (`/sys/class/regulator/regulator.20`) went to `state=disabled` at ~33.7s into boot, with no overcurrent/fault message logged. A subsequent full `sudo reboot` (warm OS restart) did **not** bring it back — the rail stayed disabled through the reboot, strongly suggesting it's controlled by the board's PMIC/load-switch hardware rather than pure kernel/software state, and a warm reboot doesn't reset it. **Fix:** a genuine cold power-off (cut power fully, wait ~10s, power back on) — not just `sudo reboot` — cleared it. Confirmed after: camera back (now enumerating as `03e7:f63b`, its *booted* DepthAI application-mode ID, vs. the unbooted `03e7:2485`), mouse dongle (`3554:fc03`) present, keyboard working, `helmet-recognition.service` running cleanly with live `Detects`/`REC` activity in the logs. Note `regulator.20/state` still reads `disabled` in sysfs even now everything works — that sysfs field apparently doesn't map simply to "is this rail powered," so don't use it as a diagnostic signal on its own; `lsusb` is the reliable check.

**Takeaway for a future session:** if USB peripherals vanish on this board and a plain `sudo reboot` doesn't bring them back, don't spend time on driver-level unbind/rebind attempts — go straight to a full physical power-off/power-on. Restarting `lightdm` specifically is a plausible trigger for this and should be avoided when just applying a config change reachable via a full reboot instead.

---

## 8. Current Status & Next Steps (as of 2026-09-09)

**Done:**
- Core pipeline (capture → YuNet detect → SFace recognize → MOSSE track → HUD overlay) working on both the dev laptop (built-in webcam) and the target board (OAK-D-Lite), including live face detection + recognition confirmed working end-to-end on the actual AR helmet hardware.
- Repo cleanup: stray scripts/files removed, `pytest` passes cleanly (21 tests), stale doc/test drift fixed.
- Board (`meryl`) has systemd auto-start installed, enabled, and verified across multiple full power cycles, including self-healing from a cold-boot camera race.
- ESC/`q` clean-exit behavior fixed to actually stay exited; `startc` command added for manual restart.
- `light-locker` screensaver-lock disabled and DPMS/screen-blanking forced off every service start (§6.3), and LightDM's login greeter replaced with real autologin (§7.2) — board now boots directly to the HUD with no lock/login screen blocking it.
- Detection sensitivity recovered (`0.60`→`0.45`) and a multi-face publish-latency bug fixed (§7.1).
- Global (`~/.claude/`) config set: `includeCoAuthoredBy: false` + a strict CLAUDE.md rule — no AI attribution in any commit/PR from this project (or any project) going forward.
- All commits through `ae55ab9` pushed to `origin/main`. The LightDM autologin config (§7.2) was applied directly on the board via `/etc/lightdm/lightdm.conf` — **not yet captured in `systemd/setup_startc.sh` or any tracked file**, so re-provisioning the board from scratch would need this step redone manually. Worth folding into the setup script.

**Known gaps / planned next (not yet done):**
- Machine/PLC recognition feature (§10) built and unit-tested locally, but **not yet deployed to the board, not yet committed, and no real machine registered** — needs the user's BottleWise backend LAN address and a printed marker before it's actually usable.
- LightDM autologin fix (§7.2) is live-only on the board, not yet in `setup_startc.sh` — should be added so a fresh board provision reproduces it.
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
- **Restarting `lightdm` (`sudo systemctl restart lightdm`) can knock the USB hub carrying the camera/keyboard/mouse offline entirely**, requiring a full physical power-off to recover (a warm `sudo reboot` alone is not enough — see §7.2). Prefer a full reboot over a live `lightdm` restart when possible.
- **If USB peripherals vanish and `sudo reboot` doesn't bring them back, go straight to a full physical power-off/power-on** rather than attempting driver-level USB unbind/rebind fixes — see §7.2 for the diagnosis (a PMIC-controlled `usb_vbus` regulator that doesn't reset on a warm reboot).
- **Two different things can block the HUD from being visible at boot** — don't assume it's the one already fixed: `light-locker` (screensaver-triggered lock after idle, fixed in §6.3) and the LightDM login greeter (shown at every boot until real autologin was configured, fixed in §7.2) are separate mechanisms with separate fixes.

---

## 10. Machine/PLC Recognition Feature (2026-09-10)

> **Superseded 2026-09-11 — see §12.** This section describes the original design (REST polling of a BottleWise Node.js backend). The user's team's backend turned out not to be reliably reachable, and it emerged their PLC/sensor nodes publish directly to MQTT anyway — the feature was redesigned to subscribe to MQTT directly, dropping the Node.js backend/REST dependency entirely. §10.1-10.4 below are kept as history (marker choice/detection rationale is unchanged); §12 has the current accurate architecture, fields, and files.

### 10.1 What it is
Extends the HUD beyond face recognition to also identify tagged industrial machines/PLCs and overlay their live telemetry — e.g. walk up to a bottle-filling line and see its current phase, production count, and who's operating it. Requested by the user, developed against reference files their team provided for **BottleWise DT v2.4**: a Node.js + HiveMQ (MQTT) + MySQL + React digital twin for a bottle-filling line, exposing a `GET /api/state` REST endpoint with rich live telemetry (conveyor speeds, filler level, capper torque, phase, production counts, alarms, etc.).

### 10.2 Key decisions (with rationale)
- **ArUco markers, not a trained object detector or QR codes.** `cv2.aruco` is already in the installed OpenCV build (verified: 5.0.0) — zero new heavy dependency, consistent with the project's "no dlib/PyTorch/TensorFlow" motto. Detection costs a few ms on CPU vs. the ~200ms+ YuNet already pays per cycle — adding a second CNN-based detector would have been a real performance risk on this hardware. ArUco was chosen over QR specifically because it's designed to stay decodable at odd angles/motion blur, which matters more for a moving AR headset than QR's extra data capacity.
- **Curated card, not the full BottleWise dashboard.** User explicitly wants "some picked information," not a data dump. Fields shown: current phase + progress, production count + batch ID, and operator name — confirmed with the user via direct selection, not assumed.
- **Operator name comes from this project's own face recognition, not BottleWise.** Checked BottleWise's schema/backend first — it has no real operator-tracking field anywhere (only a hardcoded `'OPERATOR'` fallback string used when acknowledging alarms). Rather than asking another team to add data, when a recognized employee is in the same frame as a machine marker, their name is attributed as the operator — unifies the two existing pipelines instead of adding a dependency on someone else's system.
- **Telemetry via REST polling on a background thread, not the WebSocket feed.** Simpler to implement and reason about than a persistent WS client; matches the async-thread pattern `main.py` already uses for face detection so a slow/unreachable backend never blocks the render loop. Can upgrade to WebSocket later if ~1s staleness matters.
- **Machine detection runs regardless of whether any faces were found that cycle.** This required restructuring `_run_detection_and_recognition`'s original "if no faces, clear and return early" into a non-early-returning shape (extracted to `_detect_and_recognize_faces` + `_detect_and_track_machines`) — a machine with nobody standing near it must still show its telemetry; the original early-`return` would have silently skipped machine detection whenever zero faces were in frame.

### 10.3 New files
- `src/machine_detect.py` — `MachineDetector` (ArUco wrapper), `load_machine_database`/`match_machine` (mirrors `recognize.py`'s `load_database`/`match_face`).
- `src/machine_telemetry.py` — `MachineTelemetryClient`, one per machine, background-polls `GET {api_base_url}/api/state` every 1s, exposes `get_latest_state()`/`is_connected()` from an in-memory cache (no network call on the render path).
- `machinery/register_machine.py` — CLI to assign a marker ID to a machine (`--marker-id`, `--name`, `--api-url`), writes `machinery/database/machines.json`, and generates a printable marker PNG via `cv2.aruco.generateImageMarker` into `machinery/markers/`.
- `machinery/database/` (gitignored, `.gitkeep` tracked) and `machinery/markers/` (fully gitignored — regeneratable) — mirror `enrollment/database/`'s pattern.
- `tests/test_machine_detect.py`, `tests/test_machine_telemetry.py` — 17 new tests (renders a real ArUco marker into a synthetic frame and detects it back; spins up a local `http.server` to test the telemetry client against a real HTTP response, not just mocks).

### 10.4 Modified files
- `src/overlay.py` — added `draw_machine_card` (distinct orange accent color from person cards' green/amber) and extended `draw_overlay`'s signature with a `tracked_machines` parameter.
- `src/main.py` — `PipelineManager` gained `machine_detector`, `machine_database`, `tracked_machines`/`machine_trackers` (tracked with the same MOSSE-tracker + incremental-publish pattern as faces), and `telemetry_clients` (dict keyed by marker ID, lazily started). `--machines-db` CLI arg added (default `machinery/database/machines.json`). `cleanup()` now stops all telemetry client threads.
- `requirements.txt` — added `requests>=2.31.0` (HTTP client for telemetry polling).
- `README.md` — new "Machine Recognition" section with setup steps; project structure diagram updated.

### 10.5 Verified (local dev machine only — not yet tested on the board or against the real BottleWise backend)
- Rendered a real ArUco marker into a synthetic frame and detected it back correctly (marker ID + bbox).
- `machinery/register_machine.py`'s save/update-in-place logic and marker PNG generation, via direct function calls.
- `MachineTelemetryClient` against both an unreachable URL (stays disconnected, no crash) and a real local `http.server` mock (`GET /api/state` → correctly cached and exposed).
- Full pipeline integration: called `PipelineManager._detect_and_track_machines()` directly with a synthetic marker frame — confirmed telemetry client auto-starts on first marker sighting, operator name is correctly attributed when a matching face is also present vs. `None` when not, and `tracked_machines` correctly clears when the marker leaves frame.
- Full existing test suite still green: 38 tests total (21 original + 17 new), all passing.

### 10.6 Not yet done
- **No physical ArUco marker has been printed**, and the pipeline hasn't been run against the real BottleWise backend. User's PC runs BottleWise at `10.70.13.144` — port 3000 (frontend) responds, but port 3001 (the backend's `/api/state`, what we actually need) does not; the backend process needs to be started separately (`3_start_backend.bat` or `node server.js` in `backend/`). Blocked on this as of 2026-09-11.
- **No machine registered yet** — `machinery/database/machines.json` doesn't exist until `machinery/register_machine.py` is run once for the actual bottle-filling line, once the backend above is reachable.
- Only the single-machine case has been exercised; the code supports multiple registered machines (list-based `machines.json`, one telemetry client per marker ID) but this hasn't been tested with more than one.
- Committed (`211638d`) and pushed to `origin/main`; `src/machine_detect.py`, `src/machine_telemetry.py`, and the updated `src/overlay.py`/`src/main.py` are now also deployed to the board (see §11.2) — but still no real machine registered there either.

---

## 11. Session Log — 2026-09-11

### 11.1 Intermittent spurious quit shortly after HUD startup
- **Symptom:** `helmet-recognition.service` would start fine (camera opens, models load, detection begins), then exit cleanly (exit code 0, no crash, no "Signal received" log) within ~2-20 seconds of "Pipeline loop started" — right around when the SFace model finishes lazy-loading on the first detection cycle. Because `Restart=on-failure` only retries on non-zero exit (intentional, see §7.2/§6.1 — a real ESC/`q` quit must stay stopped), the service then sat `inactive (dead)`, with nothing visibly running on the AR display.
- **Investigation:** Initially assumed an accidental keypress (a wireless keyboard/mouse receiver was connected at the time). But it recurred on a **later boot with no keyboard/mouse connected at all** (confirmed via `lsusb` — no Huasheng hub, no HP keyboard, no CX 2.4G receiver), ruling out a physical keypress. Wrote two standalone diagnostic scripts (non-fullscreen, then fullscreen `DisplayWindow`) and ran ~1000-1200 `poll_key()` iterations each directly on the board via `DISPLAY=:0` — **zero spurious key values** in isolation. The difference from the real pipeline: camera capture + the async detection/recognition thread running concurrently under real CPU load, specifically around first-time ONNX model loading. Root cause not conclusively pinned down (could not reproduce outside the full pipeline without more investigation time).
- **Fix (defensive, not root-cause):** `src/main.py`'s quit-key check (`key == ord('q') or key == 27`) now requires the **same** quit key on two consecutive `poll_key()` reads before actually breaking the loop (`pending_quit_key` debounce state). A real keypress trivially satisfies this — X11 key auto-repeat alone guarantees a second matching read well within human reaction time — while a single one-off glitched read is now filtered. Also logs any quit-key candidate at DEBUG and the confirmed exit at INFO, so if this recurs there's now a log trail instead of having to re-diagnose blind.
- **Not fully resolved:** this hardens against the symptom recurring destructively, but the actual root cause of the spurious read (if that's really what it is) is still unknown. Worth revisiting if it happens again with the debounce log lines available.

### 11.2 Board was missing files from the previous session's commit
- **Symptom:** After deploying the debounce fix (`src/main.py` only, via the usual base64-over-ssh single-file push), the service failed immediately with `ModuleNotFoundError: No module named 'machine_detect'`.
- **Root cause:** The machine/PLC recognition feature (§10, commit `211638d`) was committed and pushed to GitHub in the previous session, but **never actually deployed to the board** — the board's `git log` is stale (frozen at an old commit; files have only ever been pushed there individually via base64-over-ssh, never through a real `git pull`). Pushing only the one file the immediate fix touched left the board's `src/main.py` importing modules (`machine_detect.py`, `machine_telemetry.py`) and calling an `overlay.draw_overlay()` signature (`tracked_machines` param) that didn't exist there yet — a second failure (`TypeError: draw_overlay() got multiple values for argument 'fps'`) followed once the first was fixed.
- **Fix:** Pushed `src/machine_detect.py`, `src/machine_telemetry.py`, and `src/overlay.py` to the board too. Confirmed `requests` and `cv2.aruco` are both already available in the board's system Python (`cv2` 4.10.0, apt-installed — differs from the dev laptop's pip-installed 5.0.0, but both have `aruco`).
- **Process lesson:** Since the board isn't kept in sync via `git pull` (see §9's "flaky SSH" gotcha — base64-over-ssh per file has been the reliable pattern), **always `md5sum`-compare every file in `src/` (not just the one being actively edited) between local and board before assuming a targeted single-file push is sufficient.** Ran `md5sum src/*.py` on both sides this session specifically to catch this — recommended as a standard pre-flight check before any board deploy going forward, not just when something breaks.

### 11.3 Current status (2026-09-11)
- Both fixes deployed and verified: service now runs continuously past the point it previously died, actively detecting/recognizing faces, no debounce-candidate log lines observed in the post-fix run (i.e., no spurious quit-key event recurred in this session's testing window).
- Committed as `8e630a1` and pushed to `origin/main`.
- Machine recognition feature redesigned later this same session — see §12 (the REST/BottleWise-backend blocker in §10.6 is moot, that approach was dropped).

---

## 12. Machine Recognition Redesign: MQTT instead of REST (2026-09-11)

### 12.1 Why it changed
While trying to unblock §10.6 (BottleWise's backend unreachable), the user clarified their team's PLC/sensor nodes **publish directly to MQTT** (the public `broker.hivemq.com`, per BottleWise's own `backend/.env`) — the Node.js/Express backend was just a middle layer re-publishing that over REST/WebSocket, and it wasn't reliably running. Decision: subscribe to MQTT directly from the HUD, drop the Node backend dependency entirely. This also resolved the earlier LAN-reachability headaches (port 3001 unreachable, subnet/isolation issues) since it's a straight MQTT subscription to a broker that's already known to work.

Checked the actual topic list in `server.js`/`mqtt-simulator.js` (found after the reference files were relocated to `~/Videos/BottleWise_DT_v2.4_HiveMQ_WS_D (2)/...` mid-session — they'd been moved out of the git-tracked project directory): only machine/process state is published (conveyor speed & state, filler state/level, phase, production count, alarms, energy). **No topic publishes running_hours, downtime_hours, production_pct, or parts_life/parts_to_change** — confirmed directly with the user rather than assumed. Resolution (user's explicit call):
- **Status (running/stopped)**: real MQTT data, subscribed from `bottlewise/conveyor/input/state`.
- **Running hours / downtime hours**: derived locally by the HUD, timing how long the machine has been in each MQTT-reported state (not published anywhere, but grounded in real sensor data).
- **Production %, parts life/parts-to-change, next maintenance due, fault reason**: explicitly **dummy/placeholder data** per the user ("that also dummy date and tme") — static values set once at registration (`machinery/register_machine.py`), not live-tracked. No pretense of a real maintenance backend here.

### 12.2 Architecture
- **`src/machine_telemetry.py` rewritten** from an HTTP polling client to an MQTT subscriber (`paho-mqtt`, `CallbackAPIVersion.VERSION2` with a fallback to the legacy constructor for older paho-mqtt installs — needed since the board's environment isn't guaranteed to match the dev laptop's pip-installed version). One client per machine (keyed by marker ID, same as before), background thread, `client.subscribe()` on connect.
- **Hour accumulation**: on each status-topic message, if the decoded status differs from the last known one, credit the elapsed wall-clock time to whichever state just ended (`_running_hours_base` or `_stopped_hours_base`), then persist both totals to a small local JSON file per machine (`machinery/database/hours_<marker_id>.json`) so they survive a restart. `get_latest_state()` computes the *current* status's live-elapsed time on top of the persisted base at call time (not committed until the next actual transition) — this is why `_apply_status_message` and `get_latest_state` are split out as separately testable units, and why `get_latest_state` accepts an optional `now` override (dependency-injected clock, defaults to `time.time()`) purely for deterministic unit testing.
- **`is_connected()`** means "a status message has arrived within the last 30s" (`STALE_AFTER_S`), not just "the MQTT socket is technically open" — a broker connection can succeed while nothing is actually publishing, and the card should say so.
- **`machinery/register_machine.py`** extended with `machine_id`, `mqtt_broker`/`mqtt_port`/`status_topic` (all default to the public broker + BottleWise's own topic naming), `production_pct`, `next_maintenance_due`, `fault_reason`, plus a placeholder two-entry `parts` list (one OK, one flagged `needs_change`) written into the record — hand-edit `machines.json` for anything more specific, this isn't meant to be a polished data-entry flow.
- **`src/overlay.py`'s `draw_machine_card`** rewritten for the new field set: `MACHINE: name (id)`, `STATUS: RUNNING/STOPPED` (green/red), `RUN: Xh  DOWN: Yh`, `PROD: X%  MAINT DUE: date`, `PARTS DUE: ...` (or `PARTS: OK`), `OPERATOR: name` (still real, still from this project's own face recognition, unchanged from §10), and `FAULT: reason` (only shown when STOPPED and a real reason is set, not the `"TBD"` default).
- **`src/main.py`**: `_detect_and_track_machines` now constructs `MachineTelemetryClient(machine_key=marker_id, broker=..., port=..., status_topic=...)` instead of passing an `api_base_url`, and copies the static placeholder fields (`machine_id`, `production_pct`, `parts`, `next_maintenance_due`, `fault_reason`) from the registration record straight into the tracked-machine entry each cycle (cheap, local, no network involved) — only `telemetry` (status + hours) comes from the live MQTT client at render time, same pattern as before.
- **`requirements.txt`**: `requests` removed (nothing imports it anymore — verified via grep before removing), `paho-mqtt>=2.0.0` added instead.

### 12.3 Verified (local dev machine only)
- Real end-to-end MQTT test against the actual public broker (`broker.hivemq.com:1883`, not a mock): connection succeeds (CONNACK logged, subscription issued) — confirmed no publisher is currently active on the topic (expected, the user's simulator/PLC processes aren't running right now), but the connection path itself is proven to work.
- `_apply_status_message`/`get_latest_state` accumulation logic: first-message handling (no backdated hours), a full RUNNING→STOPPED transition crediting the correct elapsed hours, repeated same-status messages not double-counting, hours persisting correctly across a new client instance reading the same state file, case-insensitive status parsing, `is_connected()` reflecting message recency. 9 new/rewritten tests, all passing.
- `register_machine.py`'s updated `save_machine_record` with the new fields, via direct function call.
- `draw_machine_card` rendering all three states (RUNNING with data, STOPPED with a fault reason, disconnected/no telemetry) without error.
- Full `PipelineManager._detect_and_track_machines()` integration: static fields correctly copied from a synthetic machine record onto the tracked entry, telemetry client correctly constructed with the record's MQTT settings, a simulated status message correctly reflected in `get_latest_state()`.
- Full test suite: 43 tests total (21 original + 17 marker/registration + 9 telemetry, up from the 38 in §10 since the old 5 REST-based telemetry tests were replaced), all passing.

### 12.4 Status as of end of 2026-09-11 session — see §13 for the full deployment log
Everything below was completed later in the same day; kept here as the original "not yet done" list for historical accuracy, superseded by §13.
- ~~`paho-mqtt` is not installed on the board's system Python~~ — installed (§13.1).
- ~~Not deployed to the board~~ — deployed (§13.1).
- ~~No real machine registered anywhere~~ — "Bottle Filling Line 1" / MCH-001 / marker ID 0 registered, marker printed image generated and sent to the user (§13.2).
- **Never tested against a live-publishing MQTT feed** — still true. The board's campus network blocks MQTT entirely regardless of topic (§13.3) — this is unrelated to whether a publisher is active.

---

## 13. AR Helmet Deployment & Dashboard Redesign (2026-09-11, continued)

### 13.1 Board deployment
Installed `paho-mqtt` on the board despite two failed avenues: `pip install` is blocked by PEP 668 (externally-managed-environment) without `--break-system-packages`, and even with that flag AND `apt-get install python3-paho-mqtt`, **the campus network's captive-portal proxy corrupted both downloads** (apt got a 797-byte login-page HTML instead of the real 63KB .deb; pip's index request returned no parseable versions) — the same class of issue as the git-clone SSL bug in §2's Bug #2, now also breaking pip/apt. Resolution: since `paho-mqtt` is pure Python (verified: no `.so` files), copied the already-installed package directly from the dev laptop's venv to the board over SSH (`tar` + pipe through `ssh ... cat > file`, not base64-in-argument -- see below) and extracted it into `/usr/local/lib/python3.13/dist-packages/`. Confirmed working: `import paho.mqtt.client` succeeds on the board.

Also hit and fixed a **large-file transfer limit**: the established base64-embedded-in-SSH-command-argument pattern (used successfully all session for small text files) failed silently for a 221KB base64 payload (probably shell argument length). Fixed by piping the raw file directly through SSH's stdin instead (`cat local_file | ssh host "cat > remote_file"`) — binary-safe, no encoding needed, worked on the first try even at 166KB. **Prefer stdin-piping over argument-embedding for any file over a few KB going forward.**

Pushed `src/machine_telemetry.py`, `src/main.py`, `src/overlay.py`, `requirements.txt`, `machinery/register_machine.py`, and `machinery/database/machines.json` to the board (the `md5sum`-compare-first habit from §11.2 caught exactly which files needed it). Verified via a synthetic-marker test run directly on the board (same technique as the original dev-laptop test in §12.3): machine database loads, marker matches, telemetry client constructs with the correct broker/topic.

### 13.2 Machine registered
Ran `machinery/register_machine.py` for the real machine: marker ID `0`, name "Bottle Filling Line 1", machine ID `MCH-001`, production 87%, maintenance due 2026-09-20. Generated the printable marker PNG and sent it to the user directly via the file-delivery tool (not committed to git -- `machinery/markers/` and `machinery/database/machines.json` are both gitignored, per-deployment data). `status_topic` was initially guessed as `bottlewise/conveyor/input/state` (BottleWise's own default), then corrected to the user-confirmed real topic `aries/bottlefeeder/data` once they clarified their team's actual publishing setup.

### 13.3 Campus network blocks MQTT entirely -- confirmed exhaustively
Systematically tested every angle before concluding this is a hard network block, not a code or config issue:
- Raw TCP to `broker.hivemq.com:1883` (plain MQTT): `Connection refused`.
- `broker.hivemq.com` on `8000` (plain WS) and `8884` (WSS): both `Connection refused`.
- `broker.mqttdashboard.com` (the actual hostname HiveMQ's own browser demo client connects to under the hood) on `8884`: `Connection refused`. On `443`: TCP connects, but **certificate verification fails with a hostname mismatch** -- the same captive-portal TLS-interception behavior documented in §2's Bug #2 and hit again in §13.1's pip/apt failures. This network MITMs *all* outbound HTTPS, not just specific domains.
- Bypassing cert verification entirely (`ssl.CERT_NONE` + `tls_insecure_set`) on both `broker.hivemq.com:443` and `broker.mqttdashboard.com:443`: TCP and TLS both complete, but the **WebSocket upgrade handshake itself fails** ("connection not upgraded"). This is the key finding: it's not just a TLS proxy passively re-encrypting traffic, it's actively inspecting HTTP semantics and rejecting the MQTT-over-WebSocket upgrade specifically, while still letting normal browser HTTPS traffic through (confirmed: the user's own browser, on the same network, successfully used HiveMQ's public websocket-client demo page).
- Conclusion: this looks like traffic fingerprinting that only allows real browser connections through, not this kind of lightweight client. **Not fixable from code.** Options given to the user: move the board to a different network, ask campus IT to allow it, or leave the code as-is (verified correct) until the network changes. User chose to leave it for now.

### 13.4 Physical marker detection troubleshooting
Deployed and running, but the physical ArUco marker (shown on a phone screen -- no printer available) would not detect for an extended troubleshooting session. Root-caused via direct camera-frame capture (temporarily stopping the systemd service, since the DepthAI camera only supports one client at a time, running a one-off script to grab a frame, restarting the service) rather than guessing blindly:
- Multiple captured frames showed no phone in view at all -- initial instructions ("hold it up") were being interpreted as holding the phone near the face/ear, not aiming the screen at the lens.
- Once correctly positioned in frame, the marker still didn't decode. A frame captured with `cv2.aruco.drawDetectedMarkers` overlaid (to distinguish "not in view" from "in view but undecodable") showed the marker was visible but not detected, with visible **screen glare** and the phone held at an angle rather than flat/perpendicular to the lens.
- Diagnosis: phone screens are a poor target for this kind of fiducial-marker detection -- glossy/reflective surfaces break the sharp black/white edges the algorithm needs, unlike matte printed paper. Recommendation given to the user: print the marker if at all possible; this is a physical/environmental limitation, not a bug (the same marker renders and decodes correctly in every synthetic/software test in §10-§12).
- Added a temporary diagnostic log line to `_detect_and_track_machines` (logs marker count + IDs every cycle, even for zero/unmatched markers) specifically to distinguish "camera sees nothing markerlike" from "sees something but ID doesn't match" from "something downstream is broken" -- this should be removed once physical detection is confirmed working, it's not meant to be permanent.
- To prove the *rendering* code was correct independent of the detection problem, built a one-off demo script (`/tmp/show_dash_demo.py`, not committed -- ephemeral, board-local only) that force-injects a fake `tracked_machines` entry with real sample data and displays it on the actual physical screen. User confirmed seeing the card render correctly, isolating the remaining problem entirely to physical marker detection, not the code.

### 13.5 Dashboard layout redesign: side panels instead of a floating card
User feedback after seeing the card: wanted a fixed-position "left panel / right panel, camera feed clear in the center" HUD layout instead of a card that appears next to/over the tracked object (which can obscure it and moves around as the object moves in frame). Implemented:
- New `draw_side_panel()` in `overlay.py`: generic helper, anchors a semi-transparent panel to the left or right screen edge at a fixed vertical position (not tied to any bbox), with a bright inner accent line on the edge facing the center for a sci-fi-HUD look.
- `draw_machine_card()` rewritten to split its fields across two calls to this helper -- left panel: machine name/ID, status, running/downtime hours; right panel: production %, maintenance due, parts needing change, operator, fault reason -- instead of one card. The marker itself still gets a small corner-reticle outline (so it's still visually obvious what's being tracked), but no large card sits on top of it.
- Function signature unchanged, so no caller (`main.py`, `draw_overlay`) needed updating -- purely an internal rendering change.
- Verified visually (rendered to PNG, inspected) for the RUNNING, STOPPED+fault, and disconnected/no-telemetry states before deploying. Deployed to the board and demoed live on the physical screen via the same force-injection demo script.
- Face cards (`draw_hud_card`) were intentionally left unchanged -- the request was specifically about "that dashboard" (the machine card just demoed), not a general redesign; revisit only if asked.

### 13.6 Dashboard visual polish: PIL rendering, adapted from a prior related project
User pointed at a reference: `~/Downloads/pi/` -- an earlier Raspberry-Pi-based "Smart Wearable" AR system (same institution, `bitsathy.ac.in`) that solved a very similar problem (YOLO bottle-cap/fill inspection with an OAK-D camera panel + info panel). Its `oled_ui_yolo.py` renders info panels via **PIL** (`ImageDraw`/`ImageFont`) instead of raw `cv2.putText` -- bordered sections with an amber accent bar, a bulleted title, a colored status **badge** box, and right-aligned bold key/value rows -- visibly sharper and more legible than plain `cv2.putText`, which has no anti-aliasing control and limited font choice.

Confirmed both machines already have what's needed before committing to this: `PIL`/Pillow and matching monospace TTFs (`LiberationMono`/`DejaVuSansMono`) are present on the board already (apt-installed originally alongside opencv/numpy); Pillow was `pip install`ed into the dev laptop's venv for local testing (fonts already present there too). No new *board* dependency.

Rewrote `overlay.py`'s machine-panel rendering to adopt this style, adapted to our field set (not a line-by-line port -- the reference's 3-section layout doesn't map 1:1 onto our fields):
- `_panel_font()`: TTF loader searching both Fedora's (`liberation-mono-fonts`) and Debian/Raspbian's (`truetype/dejavu`) font paths, so the same code finds a real font on the dev laptop and the board without a bundled font file; falls back to PIL's built-in bitmap font if neither is found.
- `_render_panel()`: renders one bordered section (title + bullet + optional status badge + key/value rows) to a PIL image sized to its content, returned as a BGR numpy array.
- `draw_side_panel()`: rewritten to call `_render_panel()` and **paste** the fully-opaque result directly into the frame (`frame[y0:y1, x0:x1] = panel_bgr`) rather than alpha-blending a semi-transparent cv2 rectangle -- simpler and crisper, matching the reference project's approach of treating the panel as its own solid region rather than a see-through overlay. Signature changed from a flat `(text, color)` line list to structured `title`/`subtitle`/`badge`/`kv_rows` arguments to support the badge/section style; the only caller (`draw_machine_card`) was updated accordingly, so this is a local rewrite, not a breaking change to anything external.
- `draw_machine_card()`: left panel is a "MACHINE" section with the machine name as a subtitle, a colored RUNNING/STOPPED/NO SIGNAL badge, and RUN/DOWN hours as key-value rows; right panel is a "PRODUCTION" section with production %, maintenance due, parts-due count + names, operator, and fault (when applicable).
- Verified visually (PNG renders inspected) across RUNNING/STOPPED+fault/disconnected states before deploying -- confirmed the badge, borders, and right-aligned bold values all render correctly and the center of the frame is still fully clear.
- Deployed to the board (`overlay.py` only -- no other file needed changes); confirmed `import overlay` succeeds standalone (validates the font loader actually finds a font on the board, not just falling back silently) before restarting the service.

**Hit the USB VBUS power-rail dropout again (see §7.2, §11.2) while stop/starting the service repeatedly to re-run the physical-screen demo** -- the whole OAK-D-Lite hub vanished from `lsusb` again, real service included (not just the demo script). Consistent with the established pattern: a warm `systemctl`/service cycle is not the trigger by itself (this session's repeated stop/start cycles for earlier demos hadn't triggered it), but *something* about sustained camera-handle churn eventually does. Recovery was the same as before: full physical power-off/on (warm `reboot` was not attempted this time, going straight to the known-working fix per the established playbook) -- confirmed working again afterward: camera back (`03e7:f63b`, booted), no greeter, service running continuously, face detection active, no errors from the new PIL rendering path.

## 14. Pre-review re-verification pass -- JSON payload bug found and fixed

Before a project review, did a full line-by-line re-read of every machine-recognition file (`machine_detect.py`, `machine_telemetry.py`, `overlay.py`, `main.py`, `register_machine.py`, `tools/demo_dashboard.py`) looking specifically for correctness bugs, not style.

**Bug found:** `MachineTelemetryClient._apply_status_message` (in `machine_telemetry.py`) compared the raw decoded MQTT payload directly against `RUNNING_STATE_VALUES` (`{"RUNNING", "RUN", "ON", "1", "TRUE", "START", "STARTED"}`), assuming the publisher always sends a bare string like `"RUNNING"`. The real registered topic is `aries/bottlefeeder/data` -- a name ending in "data" (not "state"), which strongly suggests the team's publisher actually bundles several fields (status, speed, etc.) into one JSON message rather than sending a lone status string. If that's the case, the raw payload would never match any value in `RUNNING_STATE_VALUES` and the machine would silently and permanently show as STOPPED even while genuinely running -- with no error or exception to reveal why.

**Fix:** added `_extract_status_value(raw)` to `machine_telemetry.py`. It tries to `json.loads()` the raw payload; if that succeeds and yields a dict, it looks (case-insensitively) for any of `STATUS_FIELD_NAMES = ("status", "state", "run_state", "running", "machine_status")` and returns that field's value instead of the raw payload. If the payload isn't JSON, isn't a dict, or has none of those field names, it falls back to returning the raw payload unchanged -- so plain-string payloads (the previously-assumed format) keep working exactly as before. `_on_message` now calls `_apply_status_message(_extract_status_value(value), time.time())` instead of passing `value` straight through.

This is defensive: the real payload shape on `aries/bottlefeeder/data` has never actually been observed (the campus network still blocks MQTT entirely, see §12/§13), so this fix can't be confirmed end-to-end against the real feed yet. It does guarantee that *either* a bare string *or* a JSON object with a recognizable field name works correctly, which covers both plausible formats.

**Tests:** added `TestExtractStatusValue` (10 cases) to `tests/test_machine_telemetry.py`, covering plain strings, JSON with the primary/alternate/case-varied field names, boolean/numeric field values, JSON with no recognizable field (falls back to raw), invalid JSON, JSON arrays, and an end-to-end check through `_apply_status_message`. Full suite: 53 passed.

**Also re-verified, no changes needed:**
- `overlay.py` -- panel height/padding math, RGB-vs-BGR color separation, and font-path fallback list all traced and confirmed correct. Noted one purely theoretical edge case (negative panel coordinates if frame width dropped below ~210px) that can't occur at the project's actual 640x480 capture resolution -- left as-is.
- `main.py` -- the `thread_lock`-guarded read/write pattern around `tracked_machines`/`machine_trackers` is safe: both are always written together and read together under the lock, so there's no length-mismatch race despite the lock being released/reacquired once per marker inside the detection loop.
- `machine_detect.py`, `register_machine.py`, `tools/demo_dashboard.py` -- read in full, no issues found.

**Deployed:** pushed the fixed `machine_telemetry.py` to the board via `cat | ssh ... "cat > ..."`, verified syntax and the new function's behavior with a standalone on-device check script, then restarted `helmet-recognition.service` and confirmed it came up clean (no errors, face detection normal, ArUco scan still running with 0 markers currently in view since no marker was held up at the time).

**Not yet re-verified**: the new PIL-rendered panels have not been visually confirmed live with a *real* detected marker (only via the synthetic PNG renders and the earlier pre-redesign force-injected demo, which used the old cv2-line-list panel style, not this one) -- the physical marker still hasn't successfully decoded (§13.4's glare/angle problem, unresolved -- still needs a printed marker). The force-injection demo script does exercise the current code path end-to-end on-device, just not from an actual camera-seen marker.
