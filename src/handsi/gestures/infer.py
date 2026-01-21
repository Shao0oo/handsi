"""
Thread 3: Gesture inference thread.

Pops features from FeatureQueue, detects gestures, applies temporal smoothing,
and pushes to GestureQueue. Also handles habit awareness detection when enabled.
"""

import threading
from typing import Optional

from handsi.core.bus import (
    FeatureQueue,
    FeatureVector,
    GestureEvent,
    GestureQueue,
    RuntimeState,
)
from handsi.core.config import GestureConfig, HabitAwarenessConfig
from handsi.core.logging import log_debug, log_error, log_info, log_warning
from handsi.gestures.rules import GestureDetector
from handsi.gestures.smoothing import TemporalSmoother


class GestureInferenceThread(threading.Thread):
    """
    Thread 3: Gesture Inference.

    Responsibilities:
    - Pop features from FeatureQueue
    - Detect gestures using rule-based detector
    - Detect habit gestures when habit awareness is enabled
    - Apply temporal smoothing
    - Push confirmed gestures to GestureQueue
    - Update RuntimeState with latest gesture
    """

    def __init__(
        self,
        config: GestureConfig,
        feature_queue: FeatureQueue,
        gesture_queue: GestureQueue,
        runtime_state: RuntimeState,
        habit_config: Optional[HabitAwarenessConfig] = None,
        name: str = "GestureInferenceThread"
    ):
        super().__init__(name=name, daemon=True)
        self.config = config
        self.feature_queue = feature_queue
        self.gesture_queue = gesture_queue
        self.runtime_state = runtime_state
        self.habit_config = habit_config

        # Gesture detector with habit awareness thresholds
        detector_kwargs = {
            "pinch_threshold": config.pinch_threshold,
            "fist_threshold": config.fist_threshold,
            "open_hand_distance_threshold": config.open_hand_distance_threshold,
            "open_hand_spread_threshold": config.open_hand_spread_threshold,
            "swipe_velocity_threshold": config.swipe_velocity_threshold,
            "thumbs_vertical_threshold": config.thumbs_vertical_threshold,
            "confidence_threshold": config.confidence_threshold,
        }

        # Add habit awareness thresholds if config provided
        if habit_config:
            detector_kwargs.update({
                "facial_contact_distance_threshold": habit_config.facial_contact_distance_threshold,
                "facial_contact_duration_threshold": habit_config.facial_contact_duration_threshold,
            })

        self.detector = GestureDetector(**detector_kwargs)

        # Temporal smoother
        self.smoother = TemporalSmoother(
            window_size=config.smoothing_window,
            consistency_threshold=config.consistency_threshold
        )

    def run(self) -> None:
        """Main gesture inference loop."""
        log_info(f"{self.name} started")

        try:
            while not self.runtime_state.shutdown_requested:
                self._process_features()

        except Exception as e:
            log_error("GES-001", f"Unexpected error in gesture inference loop: {e}")

        finally:
            log_info(f"{self.name} stopped")

    def _process_features(self) -> None:
        """
        Process a single feature vector from the queue.

        Detects gestures, applies smoothing, and publishes confirmed gestures.
        """
        try:
            # Get feature vector from queue (blocking with timeout)
            feature_vector: Optional[FeatureVector] = self.feature_queue.get(timeout=1.0)

            if feature_vector is None:
                return

            # Detect gestures from features
            gestures = self.detector.detect_gestures(feature_vector.features)

            # Detect habit gestures if habit awareness is enabled
            if self.habit_config and self.habit_config.enabled:
                # log_info("Detecting habit gestures...")
                habit_gestures = self.detector.detect_habit_gestures(feature_vector.features)

                # Filter habit gestures based on individual toggles
                for habit in habit_gestures:
                    habit_name = habit[0]
                    if habit_name == "facial_contact" and self.habit_config.facial_contact_enabled:
                        gestures.append(habit)

            if gestures:
                log_debug(
                    f"Frame {feature_vector.frame_number}: "
                    f"Detected {len(gestures)} gesture(s): "
                    f"{', '.join(f'{g[0]}({g[1]:.2f})' for g in gestures)}"
                )

            # Apply temporal smoothing
            smoothed_gesture = self.smoother.smooth(gestures)

            if smoothed_gesture:
                gesture_name, confidence, metadata = smoothed_gesture

                # Create gesture event
                gesture_event = GestureEvent(
                    gesture_name=gesture_name,
                    confidence=confidence,
                    timestamp=feature_vector.timestamp,
                    metadata=metadata
                )

                # Push to gesture queue (non-blocking)
                # If queue is full, drop oldest gesture to keep most recent
                try:
                    self.gesture_queue.put_nowait(gesture_event)
                except Exception:
                    # Queue is full, drop oldest gesture and add new one
                    try:
                        dropped = self.gesture_queue.get_nowait()
                        log_debug(
                            f"Gesture queue full, dropped old gesture: {dropped.gesture_name}" # type: ignore
                        )
                        self.gesture_queue.put_nowait(gesture_event)
                    except Exception as e:
                        log_warning(
                            "GES-002",
                            f"Failed to manage gesture queue: {e}"
                        )
                        return

                # Update RuntimeState with latest gesture
                with self.runtime_state.lock:
                    self.runtime_state.latest_gesture = gesture_name
                    self.runtime_state.latest_gesture_confidence = confidence
                    self.runtime_state.latest_gesture_time = feature_vector.timestamp

                log_info(
                    f"Gesture confirmed: {gesture_name} "
                    f"(confidence: {confidence:.2f})"
                )
            else:
                # No confirmed gesture, clear latest in RuntimeState
                with self.runtime_state.lock:
                    if hasattr(self.runtime_state, 'latest_gesture'):
                        self.runtime_state.latest_gesture = None
                        self.runtime_state.latest_gesture_confidence = 0.0

        except Exception as e:
            # Queue timeout is normal during shutdown
            if not self.runtime_state.shutdown_requested:
                log_debug(f"Feature queue timeout or error: {e}")
