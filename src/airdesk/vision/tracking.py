"""
Thread 2: Hand tracking + feature extraction (inline).

Uses MediaPipe Hands to detect hand landmarks, extracts features,
updates RuntimeState activity level, and pushes to FeatureQueue.
"""

import threading
import time
from typing import Any, Optional

import cv2
import mediapipe as mp
import numpy as np

from airdesk.core.bus import (
    FeatureQueue,
    FeatureVector,
    FrameQueue,
    RuntimeState,
)
from airdesk.core.config import TrackingConfig
from airdesk.core.logging import log_debug, log_error, log_info, log_warning


class MediaPipeTracker:
    """
    Wrapper for MediaPipe Hands tracking.

    Handles initialization, processing, and landmark extraction.
    """

    def __init__(
        self,
        max_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5
    ):
        self.max_hands = max_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence

        # Initialize MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.hands: Optional[mp.solutions.hands.Hands] = None

    def initialize(self) -> bool:
        """
        Initialize MediaPipe Hands model.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=self.max_hands,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence
            )
            log_info("MediaPipe Hands initialized")
            return True

        except Exception as e:
            log_error("TRK-001", f"MediaPipe initialization failed: {e}")
            return False

    def process(self, image: np.ndarray) -> Optional[Any]:
        """
        Process a single frame and detect hands.

        Args:
            image: BGR image from OpenCV

        Returns:
            MediaPipe results object, or None if processing failed
        """
        if self.hands is None:
            log_error("TRK-002", "MediaPipe not initialized")
            return None

        try:
            # Convert BGR to RGB (MediaPipe expects RGB)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Process with MediaPipe
            results = self.hands.process(image_rgb)

            return results

        except Exception as e:
            log_error("TRK-003", f"MediaPipe processing failed: {e}")
            return None

    def close(self) -> None:
        """Release MediaPipe resources."""
        if self.hands is not None:
            self.hands.close()
            self.hands = None
            log_info("MediaPipe Hands closed")


def extract_features(results: Any, image_shape: tuple[int, int, int]) -> dict[str, Any]:
    """
    Extract normalized feature vector from MediaPipe landmarks.

    Args:
        results: MediaPipe results object
        image_shape: Shape of input image (H, W, C)

    Returns:
        Dictionary of extracted features
    """
    features: dict[str, Any] = {
        "hands": [],
        "hand_count": 0,
        "image_shape": image_shape
    }

    if results.multi_hand_landmarks is None:
        return features

    features["hand_count"] = len(results.multi_hand_landmarks)

    # Extract landmarks for each hand
    for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
        hand_features = {
            "landmarks": [],
            "handedness": None
        }

        # Extract (x, y, z) for each landmark (21 landmarks per hand)
        for landmark in hand_landmarks.landmark:
            hand_features["landmarks"].append({
                "x": landmark.x,
                "y": landmark.y,
                "z": landmark.z
            })

        # Extract handedness (left/right)
        if results.multi_handedness:
            handedness = results.multi_handedness[hand_idx]
            hand_features["handedness"] = handedness.classification[0].label

        features["hands"].append(hand_features)

    return features


class TrackingThread(threading.Thread):
    """
    Thread 2: Tracking + Feature Extraction.

    Responsibilities:
    - Pop frames from FrameQueue
    - Process with MediaPipe Hands
    - Extract features inline
    - Update RuntimeState activity level
    - Push features to FeatureQueue
    """

    def __init__(
        self,
        config: TrackingConfig,
        frame_queue: FrameQueue,
        feature_queue: FeatureQueue,
        runtime_state: RuntimeState,
        name: str = "TrackingThread"
    ):
        super().__init__(name=name, daemon=True)
        self.config = config
        self.frame_queue = frame_queue
        self.feature_queue = feature_queue
        self.runtime_state = runtime_state

        # MediaPipe tracker
        self.tracker = MediaPipeTracker(
            max_hands=config.max_hands,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence
        )

        # For preview window (optional)
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_landmarks: Optional[Any] = None

    def run(self) -> None:
        """Main tracking loop."""
        log_info(f"{self.name} started")

        # Initialize MediaPipe
        if not self.tracker.initialize():
            log_error("TRK-001", "Failed to initialize MediaPipe")
            return

        try:
            while not self.runtime_state.shutdown_requested:
                self._process_frame()

        except Exception as e:
            log_error("TRK-004", f"Unexpected error in tracking loop: {e}")

        finally:
            self.tracker.close()
            log_info(f"{self.name} stopped")

    def _process_frame(self) -> None:
        """
        Process a single frame from the queue.

        Performs tracking, feature extraction, and activity level update.
        """
        try:
            # Get frame from queue (blocking with timeout)
            frame = self.frame_queue.get(timeout=1.0)

            if frame is None:
                return

            # Store for preview (optional)
            self.latest_frame = frame.image.copy()

            # Process with MediaPipe
            results = self.tracker.process(frame.image)

            if results is None:
                log_warning("TRK-002", f"Tracking failed on frame {frame.frame_number}")
                return

            # Store landmarks for preview
            self.latest_landmarks = results.multi_hand_landmarks

            # Extract features inline
            features = self._extract_features(results, frame.image.shape)

            # Determine if hands are detected
            hands_detected = features["hand_count"] > 0

            # Update activity level in RuntimeState
            self.runtime_state.update_activity_level(
                hands_detected=hands_detected,
                idle_timeout=self.config.idle_timeout,
                attentive_timeout=self.config.attentive_timeout
            )

            # Create FeatureVector
            feature_vector = FeatureVector(
                features=features,
                timestamp=frame.timestamp,
                frame_number=frame.frame_number,
                hands_detected=hands_detected,
                hand_count=features["hand_count"]
            )

            # Push to feature queue (non-blocking)
            try:
                self.feature_queue.put_nowait(feature_vector)

                # Update stats
                with self.runtime_state.lock:
                    self.runtime_state.frames_processed += 1

                log_debug(
                    f"Frame {frame.frame_number} tracked: "
                    f"{features['hand_count']} hands, "
                    f"activity={self.runtime_state.activity_level.value}, "
                    f"fps={self.runtime_state.current_fps}"
                )

            except Exception:
                log_warning("TRK-005", f"Feature queue full, skipping frame {frame.frame_number}")

        except Exception as e:
            # Queue timeout is normal during shutdown
            if not self.runtime_state.shutdown_requested:
                log_debug(f"Frame queue timeout or error: {e}")

    def _extract_features(self, results: Any, image_shape: tuple[int, int, int]) -> dict[str, Any]:
        """
        Extract features from MediaPipe results.

        Args:
            results: MediaPipe results
            image_shape: Image shape (H, W, C)

        Returns:
            Dictionary of extracted features
        """
        try:
            return extract_features(results, image_shape)
        except Exception as e:
            log_error("FEA-001", f"Feature extraction failed: {e}")
            return {
                "hands": [],
                "hand_count": 0,
                "image_shape": image_shape
            }

    def get_latest_frame(self) -> Optional[tuple[np.ndarray, Any]]:
        """
        Get latest frame and landmarks for preview.

        Returns:
            Tuple of (frame, landmarks) or None
        """
        if self.latest_frame is not None:
            return (self.latest_frame, self.latest_landmarks)
        return None
