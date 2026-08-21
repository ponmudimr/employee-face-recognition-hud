"""Webcam capture wrapper and borderless fullscreen display manager for AR glass output."""

import logging
import sys
from typing import Tuple, Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class WebcamCapture:
    """Wrapper around OpenCV VideoCapture for reading USB webcam streams cleanly."""

    def __init__(self, device_index: int = 0, width: int = 640, height: int = 480, fps: int = 30) -> None:
        """Initialize webcam device.

        Args:
            device_index: V4L2 device index (default 0 for /dev/video0).
            width: Frame capture width.
            height: Frame capture height.
            fps: Frame rate target.
        """
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: Optional[cv2.VideoCapture] = None

    def open(self) -> bool:
        """Attempt to open the USB webcam device.

        Returns:
            bool: True if webcam successfully opened, False otherwise.
        """
        logger.info(f"Attempting to open camera device index {self.device_index}...")
        try:
            self.cap = cv2.VideoCapture(self.device_index)
            if not self.cap.isOpened():
                logger.error(
                    f"Failed to open video capture device /dev/video{self.device_index}. "
                    "Ensure webcam is connected and user has permission (e.g. video group)."
                )
                return False

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            logger.info(f"Webcam {self.device_index} initialized ({self.width}x{self.height} @ {self.fps} FPS).")
            return True
        except Exception as e:
            logger.error(f"Unexpected error initializing webcam {self.device_index}: {e}")
            return False

    def is_opened(self) -> bool:
        """Check if camera stream is active."""
        return self.cap is not None and self.cap.isOpened()

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read next frame from webcam.

        Returns:
            Tuple containing success boolean and frame image (BGR numpy array or None).
        """
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
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            logger.info("Webcam device released.")


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
