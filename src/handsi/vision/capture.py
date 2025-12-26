"""
Thread 1: Camera capture with adaptive FPS control.

Captures frames from webcam and pushes to FrameQueue.
Implements frame-skipping backpressure when queue is full.
Adjusts capture rate based on RuntimeState.current_fps.
"""

import threading
import time
from typing import Optional

import cv2
import numpy as np

from handsi.core.bus import Frame, FrameQueue, RuntimeState
from handsi.core.config import CameraConfig
from handsi.core.logging import log_debug, log_error, log_info, log_warning


class CaptureThread(threading.Thread):
    """
    Thread 1: Webcam capture with adaptive FPS.

    Responsibilities:
    - Open and manage camera connection
    - Capture frames at rate specified by RuntimeState.current_fps
    - Push frames to FrameQueue (drop if full)
    - Handle camera errors gracefully
    """

    def __init__(
        self,
        config: CameraConfig,
        frame_queue: FrameQueue,
        runtime_state: RuntimeState,
        name: str = "CaptureThread"
    ):
        super().__init__(name=name, daemon=True)
        self.config = config
        self.frame_queue = frame_queue
        self.runtime_state = runtime_state
        self.camera: Optional[cv2.VideoCapture] = None
        self._frame_counter = 0

    def run(self) -> None:
        """Main capture loop."""
        log_info(f"{self.name} started")

        # Open camera
        if not self._open_camera():
            log_error("CAP-001", f"Failed to open camera {self.config.device_id}")
            return

        try:
            while not self.runtime_state.shutdown_requested:
                self._capture_frame()
                self._adaptive_sleep()

        except Exception as e:
            log_error("CAP-004", f"Unexpected error in capture loop: {e}")

        finally:
            self._close_camera()
            log_info(f"{self.name} stopped")

    def _open_camera(self) -> bool:
        """
        Open camera with configured settings.

        Returns:
            True if camera opened successfully, False otherwise
        """
        try:
            self.camera = cv2.VideoCapture(self.config.device_id)

            if not self.camera.isOpened():
                return False

            # Set resolution
            width, height = self.config.resolution
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            # Verify actual resolution
            actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if (actual_width, actual_height) != (width, height):
                log_warning(
                    "CAP-003",
                    f"Requested {width}x{height}, got {actual_width}x{actual_height}"
                )

            log_info(f"Camera opened: {actual_width}x{actual_height}")
            return True

        except Exception as e:
            log_error("CAP-001", f"Camera open failed: {e}")
            return False

    def _close_camera(self) -> None:
        """Release camera resources."""
        if self.camera is not None:
            self.camera.release()
            self.camera = None
            log_info("Camera released")

    def _capture_frame(self) -> None:
        """
        Capture a single frame and push to queue.

        Implements frame-skipping if queue is full.
        """
        if self.camera is None:
            return

        try:
            # Read frame from camera
            ret, image = self.camera.read()

            if not ret or image is None:
                log_warning("CAP-005", "Failed to read frame from camera")
                return

            # Validate frame
            if image.size == 0:
                log_warning("CAP-003", "Empty frame captured")
                return
            
            if image.ndim == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            elif image.ndim == 3 and image.shape[2] == 4:
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

            # Create Frame object
            frame = Frame(
                image=image,
                timestamp=time.time(),
                frame_number=self._frame_counter
            )

            # Try to push to queue (non-blocking)
            try:
                self.frame_queue.put_nowait(frame)

                # Update stats
                with self.runtime_state.lock:
                    self.runtime_state.frames_captured += 1

                log_debug(f"Frame {self._frame_counter} captured and queued")

            except Exception:
                # Queue is full - drop frame (frame-skipping backpressure)
                log_warning("CAP-002", f"Frame {self._frame_counter} dropped (queue full)")

            self._frame_counter += 1

        except Exception as e:
            log_error("CAP-006", f"Frame capture error: {e}")

    def _adaptive_sleep(self) -> None:
        """
        Sleep based on RuntimeState.current_fps.

        This implements the adaptive FPS control.
        """
        with self.runtime_state.lock:
            target_fps = self.runtime_state.current_fps

        if target_fps <= 0:
            target_fps = 2  # Fallback

        sleep_time = 1.0 / target_fps
        time.sleep(sleep_time)
