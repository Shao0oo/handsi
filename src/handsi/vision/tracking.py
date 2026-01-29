"""
Thread 2: Holistic tracking + feature extraction (inline).

Uses MediaPipe Holistic to detect hand, face, and pose landmarks,
extracts features, updates RuntimeState activity level, and pushes to FeatureQueue.
"""

import threading
import time
from typing import Any, Optional

import cv2
import numpy as np

from mediapipe.python.solutions import holistic as mp_holistic
from mediapipe.python.solutions import hands as mp_hands
from mediapipe.python.solutions.holistic import Holistic
from mediapipe.python.solutions.hands import Hands

from handsi.core.bus import (
    FeatureQueue,
    FeatureVector,
    FrameQueue,
    RuntimeState,
)
from handsi.core.config import TrackingConfig
from handsi.core.logging import log_debug, log_error, log_info, log_warning


class HolisticTracker:
    """
    Wrapper for MediaPipe Holistic tracking (hands + face + pose).

    Handles initialization, processing, and landmark extraction for
    holistic tracking (face + pose + hands).
    """

    def __init__(
        self,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5
    ):
        self.model_complexity = model_complexity
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence

        # Initialize MediaPipe Holistic
        self.mp_holistic = mp_holistic
        self.holistic: Optional[Holistic] = None

    def initialize(self) -> bool:
        """
        Initialize MediaPipe Holistic model.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.holistic = self.mp_holistic.Holistic(
                static_image_mode=False,
                model_complexity=self.model_complexity,  # 0=lite, 1=medium, 2=heavy
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                refine_face_landmarks=True  # Include iris landmarks
            )
            log_info(f"MediaPipe Holistic initialized (model_complexity={self.model_complexity})")
            return True

        except Exception as e:
            log_error("TRK-006", f"MediaPipe Holistic initialization failed: {e}")
            return False

    def process(self, image: np.ndarray) -> Optional[Any]:
        """
        Process a single frame and detect hands, face, and pose.

        Args:
            image: BGR image from OpenCV

        Returns:
            MediaPipe holistic results object, or None if processing failed
        """
        if self.holistic is None:
            log_error("TRK-007", "MediaPipe Holistic not initialized")
            return None

        try:
            # Convert BGR to RGB (MediaPipe expects RGB)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Improve performance: mark image as not writeable
            image_rgb.flags.writeable = False

            # Process with MediaPipe Holistic
            results = self.holistic.process(image_rgb)

            # Restore writeable flag
            image_rgb.flags.writeable = True

            return results

        except Exception as e:
            log_error("TRK-008", f"MediaPipe Holistic processing failed: {e}")
            return None

    def close(self) -> None:
        """Release MediaPipe resources."""
        if self.holistic is not None:
            self.holistic.close()
            self.holistic = None
            log_info("MediaPipe Holistic closed")


class HandsOnlyTracker:
    """
    Wrapper for MediaPipe Hands tracking (hands only, no face/pose).

    Lighter weight than HolisticTracker, better performance when
    face/pose landmarks are not needed.
    """

    def __init__(
        self,
        max_hands: int = 2,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5
    ):
        self.max_hands = max_hands
        self.model_complexity = model_complexity
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence

        # Initialize MediaPipe Hands
        self.mp_hands = mp_hands
        self.hands: Optional[Hands] = None

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
                model_complexity=self.model_complexity,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence
            )
            log_info(
                f"MediaPipe Hands initialized "
                f"(max_hands={self.max_hands}, model_complexity={self.model_complexity})"
            )
            return True

        except Exception as e:
            log_error("TRK-009", f"MediaPipe Hands initialization failed: {e}")
            return False

    def process(self, image: np.ndarray) -> Optional[Any]:
        """
        Process a single frame and detect hands only.

        Args:
            image: BGR image from OpenCV

        Returns:
            MediaPipe hands results object, or None if processing failed
        """
        if self.hands is None:
            log_error("TRK-010", "MediaPipe Hands not initialized")
            return None

        try:
            # Convert BGR to RGB (MediaPipe expects RGB)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Improve performance: mark image as not writeable
            image_rgb.flags.writeable = False

            # Process with MediaPipe Hands
            results = self.hands.process(image_rgb)

            # Restore writeable flag
            image_rgb.flags.writeable = True

            return results

        except Exception as e:
            log_error("TRK-011", f"MediaPipe Hands processing failed: {e}")
            return None

    def close(self) -> None:
        """Release MediaPipe resources."""
        if self.hands is not None:
            self.hands.close()
            self.hands = None
            log_info("MediaPipe Hands closed")


def extract_holistic_features(results: Any, image_shape: tuple[int, int, int]) -> dict[str, Any]:
    """
    Extract normalized feature vector from MediaPipe Holistic landmarks.

    Args:
        results: MediaPipe Holistic results object
        image_shape: Shape of input image (H, W, C)

    Returns:
        Dictionary of extracted features (hands, face, pose)
    """
    features: dict[str, Any] = {
        "hands": [],
        "face": [],
        "pose": [],
        "hand_count": 0,
        "face_detected": False,
        "pose_detected": False,
        "image_shape": image_shape
    }

    # Extract hand landmarks (same format as MediaPipeTracker for backward compatibility)
    hand_landmarks_list = []
    handedness_list = []

    if results.left_hand_landmarks is not None:
        hand_landmarks_list.append(results.left_hand_landmarks)
        handedness_list.append("Left")

    if results.right_hand_landmarks is not None:
        hand_landmarks_list.append(results.right_hand_landmarks)
        handedness_list.append("Right")

    features["hand_count"] = len(hand_landmarks_list)

    # Extract hand features (same format as extract_features)
    for hand_idx, hand_landmarks in enumerate(hand_landmarks_list):
        hand_features = {
            "landmarks": [],
            "handedness": handedness_list[hand_idx]
        }

        # Extract (x, y, z) for each landmark (21 landmarks per hand)
        for landmark in hand_landmarks.landmark:
            hand_features["landmarks"].append({
                "x": landmark.x,
                "y": landmark.y,
                "z": landmark.z
            })

        features["hands"].append(hand_features)

    # Extract face landmarks (468 landmarks)
    if results.face_landmarks is not None:
        features["face_detected"] = True
        for landmark in results.face_landmarks.landmark:
            features["face"].append({
                "x": landmark.x,
                "y": landmark.y,
                "z": landmark.z
            })

    # Extract pose landmarks (33 landmarks)
    if results.pose_landmarks is not None:
        features["pose_detected"] = True
        for landmark in results.pose_landmarks.landmark:
            features["pose"].append({
                "x": landmark.x,
                "y": landmark.y,
                "z": landmark.z
            })

    return features


def extract_hands_only_features(results: Any, image_shape: tuple[int, int, int]) -> dict[str, Any]:
    """
    Extract feature vector from MediaPipe Hands results.

    Args:
        results: MediaPipe Hands results object
        image_shape: Shape of input image (H, W, C)

    Returns:
        Dictionary of extracted features (hands only, face/pose marked as not detected)
    """
    features: dict[str, Any] = {
        "hands": [],
        "face": [],
        "pose": [],
        "hand_count": 0,
        "face_detected": False,  # Always False for hands-only mode
        "pose_detected": False,  # Always False for hands-only mode
        "image_shape": image_shape
    }

    if results.multi_hand_landmarks is None:
        return features

    features["hand_count"] = len(results.multi_hand_landmarks)

    # Extract handedness labels
    handedness_list = []
    if results.multi_handedness:
        for handedness in results.multi_handedness:
            # MediaPipe returns "Left" or "Right"
            handedness_list.append(handedness.classification[0].label)

    # Extract hand features
    for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
        hand_features = {
            "landmarks": [],
            "handedness": handedness_list[hand_idx] if hand_idx < len(handedness_list) else "Unknown"
        }

        # Extract (x, y, z) for each landmark (21 landmarks per hand)
        for landmark in hand_landmarks.landmark:
            hand_features["landmarks"].append({
                "x": landmark.x,
                "y": landmark.y,
                "z": landmark.z
            })

        features["hands"].append(hand_features)

    return features


class TrackingThread(threading.Thread):
    """
    Thread 2: Tracking + Feature Extraction.

    Responsibilities:
    - Pop frames from FrameQueue
    - Process with MediaPipe (Holistic or Hands-only based on config)
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
        use_holistic: bool = True,
        name: str = "TrackingThread"
    ):
        super().__init__(name=name, daemon=True)
        self.config = config
        self.frame_queue = frame_queue
        self.feature_queue = feature_queue
        self.runtime_state = runtime_state
        self.use_holistic = use_holistic

        # Create appropriate tracker based on mode
        if use_holistic:
            self.tracker = HolisticTracker(
                model_complexity=config.holistic_model_complexity,
                min_detection_confidence=config.holistic_min_detection_confidence,
                min_tracking_confidence=config.holistic_min_tracking_confidence
            )
            log_info("Using HolisticTracker (hands + face + pose)")
        else:
            self.tracker = HandsOnlyTracker(
                max_hands=config.max_hands,
                model_complexity=config.model_complexity,
                min_detection_confidence=config.min_detection_confidence,
                min_tracking_confidence=config.min_tracking_confidence
            )
            log_info("Using HandsOnlyTracker (hands only - better performance)")

        # For preview window (optional)
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_landmarks: Optional[Any] = None
        self.latest_holistic_results: Optional[Any] = None

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

            # Store landmarks for preview (different access patterns for each tracker)
            hand_landmarks_list = []
            if self.use_holistic:
                # Holistic mode: separate left/right hand attributes
                if results.left_hand_landmarks is not None:
                    hand_landmarks_list.append(results.left_hand_landmarks)
                if results.right_hand_landmarks is not None:
                    hand_landmarks_list.append(results.right_hand_landmarks)
                self.latest_holistic_results = results
            else:
                # Hands-only mode: list of hands via multi_hand_landmarks
                if results.multi_hand_landmarks:
                    hand_landmarks_list = list(results.multi_hand_landmarks)
                self.latest_holistic_results = None  # No holistic data in hands-only mode
            self.latest_landmarks = hand_landmarks_list if hand_landmarks_list else None

            # Extract features inline
            h, w, c = frame.image.shape
            image_shape: tuple[int, int, int] = (int(h), int(w), int(c))
            features = self._extract_features(results, image_shape)

            # Determine if hands are detected
            hands_detected = features["hand_count"] > 0

            # Update activity level in RuntimeState
            self.runtime_state.update_activity_level(
                hands_detected=hands_detected,
                idle_timeout=self.config.idle_timeout,
                attentive_timeout=self.config.attentive_timeout, 
                fps=[self.config.fps_idle, self.config.fps_attentive, self.config.fps_active]
            )

            # Create FeatureVector
            feature_vector = FeatureVector(
                features=features,
                timestamp=frame.timestamp,
                frame_number=frame.frame_number,
                hands_detected=hands_detected,
                hand_count=features["hand_count"],
                face_detected=features.get("face_detected", False),
                pose_detected=features.get("pose_detected", False)
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
        Extract features from MediaPipe results (handles both holistic and hands-only).

        Args:
            results: MediaPipe results (Holistic or Hands)
            image_shape: Image shape (H, W, C)

        Returns:
            Dictionary of extracted features (hands, and optionally face/pose)
        """
        try:
            if self.use_holistic:
                return extract_holistic_features(results, image_shape)
            else:
                return extract_hands_only_features(results, image_shape)
        except Exception as e:
            log_error("FEA-001", f"Feature extraction failed: {e}")
            return {
                "hands": [],
                "hand_count": 0,
                "face_detected": False,
                "pose_detected": False,
                "image_shape": image_shape
            }

    def get_latest_frame(self) -> Optional[tuple[np.ndarray, Any, Any]]:
        """
        Get latest frame and landmarks for preview.

        Returns:
            Tuple of (frame, hand_landmarks, holistic_results) or None.
        """
        if self.latest_frame is not None:
            return (self.latest_frame, self.latest_landmarks, self.latest_holistic_results)
        return None
