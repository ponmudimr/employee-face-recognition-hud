"""Webcam capture wrapper and borderless fullscreen display manager for AR glass output."""

import logging
import sys
from typing import Tuple, Optional
import cv2
import numpy as np

try:
    import depthai as dai
    HAS_DEPTHAI = True
except ImportError:
    HAS_DEPTHAI = False

logger = logging.getLogger(__name__)


class DepthAICapture:
    """Wrapper around Luxonis OAK-D-Lite / DepthAI camera for reading RGB streams."""

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.device: Optional[Any] = None
        self.q_rgb: Optional[Any] = None

    def open(self) -> bool:
        if not HAS_DEPTHAI:
            logger.error("depthai library is not installed. Install with: pip install depthai")
            return False

        logger.info("Attempting to initialize Luxonis OAK-D-Lite camera via DepthAI...")
        try:
            pipeline = dai.Pipeline()
            cam_rgb = pipeline.create(dai.node.ColorCamera)

            cam_rgb.setPreviewSize(self.width, self.height)
            cam_rgb.setInterleaved(False)
            cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
            cam_rgb.setFps(self.fps)

            # Enable continuous autofocus for OAK-D-Lite-AF (autofocus variant)
            try:
                if hasattr(dai, "CameraControl") and hasattr(dai.CameraControl, "AutoFocusMode"):
                    cam_rgb.initialControl.setAutoFocusMode(dai.CameraControl.AutoFocusMode.CONTINUOUS_VIDEO)
                elif hasattr(dai, "RawCameraControl") and hasattr(dai.RawCameraControl, "AutoFocusMode"):
                    cam_rgb.initialControl.setAutoFocusMode(dai.RawCameraControl.AutoFocusMode.CONTINUOUS_VIDEO)
                logger.info("Continuous autofocus (AF) enabled for OAK-D-Lite-AF.")
            except Exception as af_err:
                logger.debug(f"Autofocus notice: {af_err}")

            # Initialize device and start pipeline (DepthAI 2.x API for RVC2)
            self.device = dai.Device(pipeline)

            self.q_rgb = self.device.getOutputQueue(cam_rgb.preview, maxSize=4, blocking=False)
            logger.info(f"OAK-D-Lite-AF (DepthAI) initialized ({self.width}x{self.height} @ {self.fps} FPS).")
            return True
        except Exception as e:
            logger.error(f"Failed to open OAK-D-Lite camera via DepthAI: {e}")
            return False

    def is_opened(self) -> bool:
        return self.device is not None

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.is_opened() or self.q_rgb is None:
            return False, None
        try:
            in_rgb = self.q_rgb.tryGet()
            if in_rgb is None:
                in_rgb = self.q_rgb.get()
            if in_rgb is not None:
                frame = in_rgb.getCvFrame()
                return True, frame
            return False, None
        except Exception as e:
            logger.warning(f"Error reading frame from OAK-D-Lite: {e}")
            return False, None

    def release(self) -> None:
        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                pass
            self.device = None
            self.q_rgb = None
            logger.info("OAK-D-Lite (DepthAI) device released.")


class WebcamCapture:
    """Wrapper around OpenCV VideoCapture or DepthAI for reading camera streams cleanly."""

    def __init__(self, device_index: int = -1, width: int = 640, height: int = 480, fps: int = 30) -> None:
        """Initialize webcam device.

        Args:
            device_index: V4L2 device index (-1 for OAK-D-Lite primary default, >=0 for V4L2 webcam).
            width: Frame capture width.
            height: Frame capture height.
            fps: Frame rate target.
        """
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: Optional[cv2.VideoCapture] = None
        self.oak_cap: Optional[DepthAICapture] = None

    def open(self) -> bool:
        """Attempt to open the camera device (supports standard USB webcam or OAK-D-Lite).

        Returns:
            bool: True if camera successfully opened, False otherwise.
        """
        # If device_index is -1 or depthai is requested/available, try OAK-D-Lite
        if self.device_index < 0:
            if not HAS_DEPTHAI:
                logger.error("DepthAI library is not installed. Cannot open OAK-D-Lite camera.")
                return False
            self.oak_cap = DepthAICapture(width=self.width, height=self.height, fps=self.fps)
            if self.oak_cap.open():
                return True
            self.oak_cap.release()
            self.oak_cap = None
            logger.error("Failed to open OAK-D-Lite camera via DepthAI.")
            return False

        logger.info(f"Attempting to open V4L2 camera device index {self.device_index}...")
        try:
            # Force V4L2 backend to bypass broken GStreamer pipelines
            self.cap = cv2.VideoCapture(self.device_index, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.device_index)

            if self.cap.isOpened():
                # Set FOURCC to MJPG for 1080p USB webcams if supported
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap.set(cv2.CAP_PROP_FPS, self.fps)

                # Warmup read to ensure stream is producing valid frames
                for _ in range(5):
                    ret, test_frame = self.cap.read()
                    if ret and test_frame is not None:
                        logger.info(f"Webcam {self.device_index} initialized ({test_frame.shape[1]}x{test_frame.shape[0]} @ {self.fps} FPS).")
                        return True

                logger.warning(f"Webcam {self.device_index} opened but failed warmup frame reads. Trying YUYV format...")
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
                ret, test_frame = self.cap.read()
                if ret and test_frame is not None:
                    logger.info(f"Webcam {self.device_index} initialized with YUYV ({test_frame.shape[1]}x{test_frame.shape[0]}).")
                    return True

            logger.warning(f"Failed to open V4L2 device /dev/video{self.device_index}.")
        except Exception as e:
            logger.warning(f"Error opening V4L2 camera {self.device_index}: {e}")

        # Fallback to OAK-D-Lite if V4L2 failed and DepthAI is installed
        if HAS_DEPTHAI:
            logger.info("V4L2 camera unavailable. Attempting DepthAI OAK-D-Lite fallback...")
            self.oak_cap = DepthAICapture(width=self.width, height=self.height, fps=self.fps)
            if self.oak_cap.open():
                return True
            self.oak_cap.release()
            self.oak_cap = None

        logger.error("No valid camera stream (V4L2 webcam or OAK-D-Lite) could be opened.")
        return False

    def is_opened(self) -> bool:
        """Check if camera stream is active."""
        if self.oak_cap is not None:
            return self.oak_cap.is_opened()
        return self.cap is not None and self.cap.isOpened()

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read next frame from camera.

        Returns:
            Tuple containing success boolean and frame image (BGR numpy array or None).
        """
        if self.oak_cap is not None:
            return self.oak_cap.read()

        if not self.is_opened():
            logger.warning("Attempted frame read on unopened camera stream.")
            return False, None

        ret, frame = self.cap.read()
        if not ret or frame is None:
            logger.warning("Failed to retrieve frame from camera stream.")
            return False, None

        return True, frame

    def release(self) -> None:
        """Release camera resources."""
        if self.oak_cap is not None:
            self.oak_cap.release()
            self.oak_cap = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            logger.info("Camera device released.")


class DisplayWindow:
    """Fullscreen borderless OpenCV window renderer for HDMI / USB-C AR Glass displays."""

    def __init__(self, window_name: str = "AR HUD Display", fullscreen: bool = True) -> None:
        """Initialize display renderer.

        Args:
            window_name: Title of OpenCV GUI window.
            fullscreen: Whether to force borderless fullscreen mode.
        """
        self.window_name = window_name
        self.fullscreen = fullscreen
        self.is_active = False

    def create(self) -> bool:
        """Create and configure OpenCV GUI window.

        Returns:
            bool: True if window successfully created, False if GUI display environment unavailable.
        """
        try:
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            if self.fullscreen:
                cv2.setWindowProperty(
                    self.window_name,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN
                )
            self.is_active = True
            logger.info(f"Display window '{self.window_name}' initialized (fullscreen={self.fullscreen}).")
            return True
        except cv2.error as e:
            logger.error(
                f"OpenCV GUI error creating display window: {e}. "
                "Ensure DISPLAY or WAYLAND_DISPLAY environment variable is configured for HDMI output."
            )
            self.is_active = False
            return False
        except Exception as e:
            logger.error(f"Failed to initialize display window: {e}")
            self.is_active = False
            return False

    def show(self, frame: np.ndarray) -> bool:
        """Render frame to HUD window.

        Args:
            frame: Image array to display.

        Returns:
            bool: True if display was successful.
        """
        if not self.is_active:
            return False

        try:
            cv2.imshow(self.window_name, frame)
            return True
        except cv2.error as e:
            logger.error(f"Error rendering frame to window: {e}")
            return False

    def poll_key(self, delay_ms: int = 1) -> int:
        """Poll keyboard input.

        Args:
            delay_ms: Wait time in milliseconds.

        Returns:
            int: Key code pressed (or -1 if no key).
        """
        if not self.is_active:
            return -1
        try:
            return cv2.waitKey(delay_ms) & 0xFF
        except cv2.error:
            return -1

    def close(self) -> None:
        """Destroy display window."""
        if self.is_active:
            try:
                cv2.destroyWindow(self.window_name)
            except cv2.error:
                pass
            self.is_active = False
            logger.info("Display window closed.")
