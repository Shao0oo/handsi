"""
Preview window for debugging and visualization.

Displays camera feed with overlaid hand landmarks and system status.
Runs in main loop (not threaded) to work on macOS.

"""

import time
from typing import Any, Optional

import cv2
import mediapipe as mp
import numpy as np

from handsi.core.bus import RuntimeState
from handsi.core.logging import log_debug, log_error, log_info


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
        window_name: str = "Handsi Preview"
    ):
        self.runtime_state = runtime_state
        self.tracking_thread = tracking_thread
        self.window_name = window_name

        # MediaPipe drawing utilities
        self.mp_hands = mp.solutions.hands # type: ignore
        self.mp_drawing = mp.solutions.drawing_utils # type: ignore
        self.mp_drawing_styles = mp.solutions.drawing_styles # type: ignore
        self.mp_face_mesh = mp.solutions.face_mesh # type: ignore
        self.mp_pose = mp.solutions.pose # type: ignore

        # Display toggles
        self.show_gestures = False  # Toggle with 'g' key
        self.show_features = False  # For detailed features (future use)

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

            frame, landmarks, holistic_results = frame_data

            # Create a copy to draw on
            display_frame = frame.copy()

            # Draw holistic landmarks (face + pose) if available
            if holistic_results is not None:
                self._draw_holistic_landmarks(display_frame, holistic_results)

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

            # Draw gesture overlay if enabled
            if self.show_gestures:
                self._draw_gesture_overlay(display_frame)

            # Display frame
            cv2.imshow(self.window_name, display_frame)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF

            # Check for 'q' key (quit)
            if key == ord('q'):
                return False

            # Check for 'g' key (toggle gesture overlay)
            if key == ord('g'):
                self.show_gestures = not self.show_gestures
                log_info(f"Gesture overlay: {'ON' if self.show_gestures else 'OFF'}")

            # Check for 'f' key (toggle detailed features)
            if key == ord('f'):
                self.show_features = not self.show_features
                log_info(f"Feature display: {'ON' if self.show_features else 'OFF'}")

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

    def _draw_holistic_landmarks(self, frame: np.ndarray, holistic_results: Any) -> None:
        """
        Draw face and pose landmarks from holistic tracking results.

        Args:
            frame: Frame to draw on (modified in-place)
            holistic_results: MediaPipe Holistic results object
        """
        # Draw face mesh (tesselation for face contours)
        if holistic_results.face_landmarks is not None:
            self.mp_drawing.draw_landmarks(
                frame,
                holistic_results.face_landmarks,
                self.mp_face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_tesselation_style()
            )
            # Draw face contours
            self.mp_drawing.draw_landmarks(
                frame,
                holistic_results.face_landmarks,
                self.mp_face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_contours_style()
            )

        # Draw pose landmarks
        if holistic_results.pose_landmarks is not None:
            self.mp_drawing.draw_landmarks(
                frame,
                holistic_results.pose_landmarks,
                self.mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
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
            latest_action = getattr(self.runtime_state, 'latest_action', None)
            actions_executed = getattr(self.runtime_state, 'actions_executed', 0)

        # Format action display (compact, with checkmark if recent)
        if latest_action:
            current_time = time.time()
            action_time = getattr(self.runtime_state, 'latest_action_time', 0.0)
            time_since_action = current_time - action_time

            # Show checkmark if action executed in last 1 second
            if time_since_action < 1.0:
                action_display = f"{latest_action} \u2713"  # ✓ checkmark
            else:
                action_display = latest_action
        else:
            action_display = "none"

        # Prepare status text (compact, 2-3 lines max)
        status_lines = [
            f"Hands: {hand_count} | FPS: {current_fps} | {activity_level.upper()}",
            f"Gestures: {'ON' if self.show_gestures else 'OFF'} (g) | Action: {action_display}",
        ]

        # Draw background rectangle for text (compact)
        line_height = 18
        overlay_height = 20 + len(status_lines) * line_height
        overlay_width = 280
        cv2.rectangle(
            frame,
            (10, 10),
            (10 + overlay_width, 10 + overlay_height),
            (0, 0, 0),
            -1  # Filled
        )
        cv2.rectangle(
            frame,
            (10, 10),
            (10 + overlay_width, 10 + overlay_height),
            (255, 255, 255),
            1  # Border
        )

        # Draw text lines (smaller font)
        y_offset = 25
        for line in status_lines:
            cv2.putText(
                frame,
                line,
                (15, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1
            )
            y_offset += line_height

        # Draw activity level indicator (color-coded circle)
        color_map = {
            "Idle": (100, 100, 100),      # Gray
            "Attentive": (0, 255, 255),   # Yellow
            "Active": (0, 255, 0)         # Green
        }
        indicator_color = color_map.get(activity_level, (255, 255, 255))

        cv2.circle(
            frame,
            (overlay_width - 5, 20),
            6,
            indicator_color,
            -1
        )

    def _draw_gesture_overlay(self, frame: np.ndarray) -> None:
        """
        Draw gesture information overlay.

        Shows:
        - Current detected gesture
        - Confidence bar
        - Color-coded by gesture type

        Args:
            frame: Frame to draw on (modified in-place)
        """
        # Get latest gesture from RuntimeState
        with self.runtime_state.lock:
            gesture_name = getattr(self.runtime_state, 'latest_gesture', None)
            confidence = getattr(self.runtime_state, 'latest_gesture_confidence', 0.0)

        if not gesture_name:
            # No gesture detected, show "None"
            gesture_display = "No Gesture"
            confidence = 0.0
            color = (100, 100, 100)  # Gray
        else:
            gesture_display = gesture_name.replace('_', ' ').upper()

            # Color-code by gesture type
            if 'pinch' in gesture_name.lower():
                color = (255, 150, 0)  # Blue-ish
            elif gesture_name.lower() in ['fist', 'open_hand']:
                color = (0, 255, 0)  # Green
            elif 'swipe' in gesture_name.lower():
                color = (0, 255, 255)  # Yellow
            elif 'two_hands' in gesture_name.lower():
                color = (255, 0, 255)  # Purple
            elif 'thumbs_up' in gesture_name.lower():
                color = (0, 200, 255)  # Orange
            else:
                color = (255, 255, 255)  # White

        h, w, _ = frame.shape

        # Position at bottom center (smaller, more professional)
        overlay_width = 280
        overlay_height = 60
        overlay_x = (w - overlay_width) // 2
        overlay_y = h - overlay_height - 15

        # Draw background rectangle (semi-transparent black)
        cv2.rectangle(
            frame,
            (overlay_x, overlay_y),
            (overlay_x + overlay_width, overlay_y + overlay_height),
            (0, 0, 0),
            -1  # Filled
        )
        cv2.rectangle(
            frame,
            (overlay_x, overlay_y),
            (overlay_x + overlay_width, overlay_y + overlay_height),
            color,
            1  # Thinner border
        )

        # Draw gesture name (smaller, cleaner font)
        text_y = overlay_y + 25
        cv2.putText(
            frame,
            gesture_display,
            (overlay_x + 15, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1
        )

        # Draw confidence bar (smaller, cleaner)
        bar_x = overlay_x + 15
        bar_y = overlay_y + 35
        bar_width = overlay_width - 80
        bar_height = 12

        # Background bar
        cv2.rectangle(
            frame,
            (bar_x, bar_y),
            (bar_x + bar_width, bar_y + bar_height),
            (40, 40, 40),
            -1
        )

        # Confidence bar (filled portion)
        filled_width = int(bar_width * confidence)
        cv2.rectangle(
            frame,
            (bar_x, bar_y),
            (bar_x + filled_width, bar_y + bar_height),
            color,
            -1
        )

        # Border around bar
        cv2.rectangle(
            frame,
            (bar_x, bar_y),
            (bar_x + bar_width, bar_y + bar_height),
            color,
            1
        )

        # Confidence percentage (smaller)
        conf_text = f"{int(confidence * 100)}%"
        cv2.putText(
            frame,
            conf_text,
            (bar_x + bar_width + 8, bar_y + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1
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
