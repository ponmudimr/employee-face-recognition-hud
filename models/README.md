# Face Recognition Models Directory

This directory stores ONNX neural network model weights for face detection and embedding extraction optimized for ARM Cortex-A53 platforms (such as the Arduino UNO Q / Qualcomm Dragonwing QRB2210).

## Recommended Models

### 1. Face Detection
- **YuNet ONNX Model (`face_detection_yunet_2023mar.onnx`)**
  - Lightweight, high performance, designed for mobile/edge processors.
  - Source: OpenCV Zoo
  - Download link: [https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
  - Direct Download:
    ```bash
    wget -O models/face_detection_yunet.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
    ```

- **Res10 SSD Caffe / ONNX (`res10_300x300_ssd_iter_140000.caffemodel` or ONNX export)**
  - Classic OpenCV DNN SSD face detector.
  - Fast baseline model for low-resolution inputs.

### 2. Face Recognition / Embeddings
- **SFace (`face_recognition_sface_2021dec.onnx`)**
  - Lightweight embedding extractor outputting a 128-dimensional embedding vector.
  - Source: OpenCV Zoo
  - Download link: [https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)
  - Direct Download:
    ```bash
    wget -O models/face_recognition_sface.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
    ```

- **MobileFaceNet ONNX (`mobilefacenet.onnx`)**
  - Extremely compact MobileNet architecture trained for ArcFace cosine loss.
  - Outputs 512-dimensional or 128-dimensional embedding vectors.

## Installation Instructions

1. Download your chosen `.onnx` model files into this directory (`models/`).
2. Update the model file path constants in `src/detect.py` and `src/recognize.py` if custom filenames are used.
3. Note: `.onnx`, `.caffemodel`, and `.pb` files in this directory are git-ignored by default.
