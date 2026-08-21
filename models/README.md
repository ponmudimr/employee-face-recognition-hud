# Face Recognition Models Directory

This directory stores ONNX neural network model weights for face detection (YuNet) and feature embedding extraction (SFace) optimized for ARM Cortex-A53 platforms (such as the Arduino UNO Q / Qualcomm Dragonwing QRB2210).

## Model Download Instructions

Run the following `curl` (or `wget`) commands from the root directory of the repository to download both models from the official [OpenCV Zoo](https://github.com/opencv/opencv_zoo) repository:

### 1. YuNet Face Detection Model
Lightweight, high-performance face detector returning bounding boxes, confidence scores, and 5-point facial landmarks.

```bash
curl -L -o models/face_detection_yunet.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
```

*Alternative using `wget`:*
```bash
wget -O models/face_detection_yunet.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
```

### 2. SFace Face Recognition Model
Compact feature extractor outputting a 128-dimensional embedding vector per face.

```bash
curl -L -o models/face_recognition_sface.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
```

*Alternative using `wget`:*
```bash
wget -O models/face_recognition_sface.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
```

---

## File Verification

After downloading, verify the files exist in `models/`:

```bash
ls -l models/*.onnx
```

Expected files:
- `models/face_detection_yunet.onnx` (~230 KB)
- `models/face_recognition_sface.onnx` (~37 MB)

*Note: All `.onnx` weight files in this directory are excluded from Git tracking via `.gitignore`.*
