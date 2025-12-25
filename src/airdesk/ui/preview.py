"""
Preview window for debugging and visualization.

Displays camera feed with overlaid hand landmarks and system status.
Runs in main loop (not threaded) to work on macOS.

NOTE: Phase 1 uses OpenCV preview in main loop for simplicity.
      Phase 2+ will use PySide6 system tray with Qt-based preview.
"""

import time
from typing import Any, Optional

import cv2
import mediapipe as mp
import numpy as np

from airdesk.core.bus import RuntimeState
from airdesk.core.logging import log_debug, log_error, log_info


class PreviewWindow:
    """
    Preview window renderer (non-threaded).

    Responsibilities:
    - Display camera feed with landmarks overlay
    - Show system status (FPS, activity level, hand count)
    - Draw feature information on frame
    - Handle keyboard input

    Must be called from main thread on macOS.
    """

    def __init__(
        self,
        runtime_state: RuntimeState,
        tracking_thread: Any,  # Reference to TrackingThread for frame access
        window_name: str = "AirDesk Preview",
        show_features: bool = False
    ):
        self.runtime_state = runtime_state
        self.tracking_thread = tracking_thread
        self.window_name = window_name

        # MediaPipe drawing utilities
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        # Feature display toggle
        self.show_features = show_features

        # Window created flag
        self._window_created = False

    def initialize(self) -> bool:
        """
        Initialize preview window.

        Returns:
            True if window created successfully, False otherwise
        """
        try:
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            self._window_created = True
            log_info("Preview window initialized")
            return True

        except Exception as e:
            log_error("GUI-001", f"Failed to create preview window: {e}")
            return False

    def update(self) -> bool:
        """
        Update preview window with latest frame.

        Should be called from main loop.

        Returns:
            False if user wants to quit (pressed 'q'), True otherwise
        """
        if not self._window_created:
            return True

        try:
            # Get latest frame and landmarks from tracking thread
            frame_data = self.tracking_thread.get_latest_frame()

            if frame_data is None:
                # No frame available yet, just process events
                key = cv2.waitKey(1) & 0xFF
                return key != ord('q')

            frame, landmarks = frame_data

            # Create a copy to draw on
            display_frame = frame.copy()

            # Draw hand landmarks if available
            if landmarks is not None:
                for hand_idx, hand_landmarks in enumerate(landmarks):
                    # Draw landmarks and connections
                    self.mp_drawing.draw_landmarks(
                        display_frame,
                        hand_landmarks,
                        self.mp_hands.HAND_CONNECTIONS,
                        self.mp_drawing_styles.get_default_hand_landmarks_style(),
                        self.mp_drawing_styles.get_default_hand_connections_style()
                    )

                    # Draw basic hand info
                    self._draw_hand_features(display_frame, hand_landmarks, hand_idx)

                    # Draw detailed features if enabled
                    if self.show_features:
                        self._draw_detailed_features(display_frame, hand_landmarks, hand_idx)

            # Draw status overlay
            self._draw_status_overlay(display_frame, len(landmarks) if landmarks else 0)

            # Display frame
            cv2.imshow(self.window_name, display_frame)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF

            # Check for 'q' key (quit)
            if key == ord('q'):
                return False

            # Check for 'f' key (toggle features)
            if key == ord('f'):
                self.show_features = not self.show_features
                log_debug(f"Feature display toggled: {self.show_features}")

            return True

        except Exception as e:
            log_debug(f"Frame rendering skipped: {e}")
            return True

    def _draw_hand_features(self, frame: np.ndarray, hand_landmarks: Any, hand_idx: int) -> None:
        """
        Draw basic feature information for a detected hand.

        Args:
            frame: Frame to draw on (modified in-place)
            hand_landmarks: MediaPipe hand landmarks
            hand_idx: Hand index (0 or 1)
        """
        # Get wrist position (landmark 0)
        wrist = hand_landmarks.landmark[0]
        h, w, _ = frame.shape
        wrist_x = int(wrist.x * w)
        wrist_y = int(wrist.y * h)

        # Draw hand label near wrist
        label = f"Hand {hand_idx}"
        cv2.putText(
            frame,
            label,
            (wrist_x + 10, wrist_y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2
        )

        # Calculate and display hand bounding box size (simple feature)
        x_coords = [lm.x for lm in hand_landmarks.landmark]
        y_coords = [lm.y for lm in hand_landmarks.landmark]

        hand_width = (max(x_coords) - min(x_coords)) * w
        hand_height = (max(y_coords) - min(y_coords)) * h

        # Display hand size
        size_text = f"Size: {int(hand_width)}x{int(hand_height)}"
        cv2.putText(
            frame,
            size_text,
            (wrist_x + 10, wrist_y + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (0, 255, 0),
            1
        )

    def _draw_detailed_features(self, frame: np.ndarray, hand_landmarks: Any, hand_idx: int) -> None:
        """
        Draw detailed feature information for a detected hand.

        Shows:
        - Hand center of mass
        - Finger tip positions
        - Key landmark coordinates

        Args:
            frame: Frame to draw on (modified in-place)
            hand_landmarks: MediaPipe hand landmarks
            hand_idx: Hand index (0 or 1)
        """
        h, w, _ = frame.shape

        # Calculate center of mass (average of all landmarks)
        x_coords = [lm.x for lm in hand_landmarks.landmark]
        y_coords = [lm.y for lm in hand_landmarks.landmark]
        z_coords = [lm.z for lm in hand_landmarks.landmark]

        center_x = int(sum(x_coords) / len(x_coords) * w)
        center_y = int(sum(y_coords) / len(y_coords) * h)
        avg_z = sum(z_coords) / len(z_coords)

        # Draw center of mass
        cv2.circle(frame, (center_x, center_y), 5, (255, 0, 255), -1)
        cv2.putText(
            frame,
            f"CoM: ({center_x}, {center_y}, {avg_z:.3f})",
            (center_x + 10, center_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.3,
            (255, 0, 255),
            1
        )

        # Draw finger tip positions (landmarks 4, 8, 12, 16, 20)
        finger_tips = [4, 8, 12, 16, 20]
        finger_names = ["Thumb", "Index", "Middle", "Ring", "Pinky"]

        for tip_idx, name in zip(finger_tips, finger_names):
            landmark = hand_landmarks.landmark[tip_idx]
            tip_x = int(landmark.x * w)
            tip_y = int(landmark.y * h)

            # Draw small circle at tip
            cv2.circle(frame, (tip_x, tip_y), 3, (0, 255, 255), -1)

            # Draw coordinate text
            coord_text = f"{name[:1]}: ({landmark.x:.2f}, {landmark.y:.2f})"
            cv2.putText(
                frame,
                coord_text,
                (tip_x + 5, tip_y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.25,
                (0, 255, 255),
                1
            )

    def _draw_status_overlay(self, frame: np.ndarray, hand_count: int) -> None:
        """
        Draw system status overlay on frame.

        Args:
            frame: Frame to draw on (modified in-place)
            hand_count: Number of hands detected
        """
        # Get stats from RuntimeState
        with self.runtime_state.lock:
            activity_level = self.runtime_state.activity_level.value
            current_fps = self.runtime_state.current_fps
            frames_captured = self.runtime_state.frames_captured
            frames_processed = self.runtime_state.frames_processed
            latch_active = self.runtime_state.latch_active

        # Prepare status text
        status_lines = [
            f"Hands: {hand_count}",
            f"Activity: {activity_level.upper()}",
            f"Target FPS: {current_fps}",
            f"Captured: {frames_captured}",
            f"Processed: {frames_processed}",
            f"Latch: {'ON' if latch_active else 'OFF'}",
            f"Features: {'ON' if self.show_features else 'OFF'} (f)"
        ]

        # Draw background rectangle for text
        overlay_height = 30 + len(status_lines) * 25
        cv2.rectangle(
            frame,
            (10, 10),
            (300, overlay_height),
            (0, 0, 0),
            -1  # Filled
        )
        cv2.rectangle(
            frame,
            (10, 10),
            (300, overlay_height),
            (255, 255, 255),
            2  # Border
        )

        # Draw text lines
        y_offset = 35
        for line in status_lines:
            cv2.putText(
                frame,
                line,
                (20, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )
            y_offset += 25

        # Draw activity level indicator (color-coded)
        color_map = {
            "idle": (100, 100, 100),      # Gray
            "attentive": (0, 255, 255),   # Yellow
            "active": (0, 255, 0)         # Green
        }
        indicator_color = color_map.get(activity_level, (255, 255, 255))

        cv2.circle(
            frame,
            (270, 30),
            10,
            indicator_color,
            -1
        )

    def cleanup(self) -> None:
        """Clean up window resources."""
        if self._window_created:
            try:
                cv2.destroyWindow(self.window_name)
                cv2.waitKey(1)  # Process window events
                log_info("Preview window closed")
            except Exception as e:
                log_debug(f"Window cleanup error: {e}")
