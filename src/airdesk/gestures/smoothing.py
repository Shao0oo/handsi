"""
Temporal smoothing for gesture detection.

Prevents flickering by requiring consistent detection over multiple frames.
"""

from collections import deque
from typing import Optional

from airdesk.core.logging import log_debug


class TemporalSmoother:
    """
    Temporal smoothing for gesture recognition.

    Requires a gesture to be detected consistently over N frames
    before confirming it. This prevents flickering between gestures.
    """

    def __init__(self, window_size: int = 3, consistency_threshold: float = 0.6):
        """
        Initialize temporal smoother.

        Args:
            window_size: Number of frames to smooth over
            consistency_threshold: Fraction of frames that must agree (0-1)
        """
        self.window_size = window_size
        self.consistency_threshold = consistency_threshold

        # Sliding window of recent gesture detections
        self.gesture_history = deque(maxlen=window_size)

        # Current confirmed gesture
        self.current_gesture: Optional[str] = None
        self.current_confidence: float = 0.0

    def smooth(self, gestures: list[tuple[str, float, dict]]) -> Optional[tuple[str, float, dict]]:
        """
        Apply temporal smoothing to gesture detections.

        Args:
            gestures: List of (gesture_name, confidence, metadata) from current frame

        Returns:
            Smoothed (gesture_name, confidence, metadata) or None if no gesture confirmed
        """
        # Get highest confidence gesture from current frame
        if gestures:
            # Sort by confidence, take highest
            gestures.sort(key=lambda x: x[1], reverse=True)
            current_gesture_name = gestures[0][0]
            current_confidence = gestures[0][1]
            current_metadata = gestures[0][2]
        else:
            current_gesture_name = None
            current_confidence = 0.0
            current_metadata = {}

        # Add to history
        self.gesture_history.append((current_gesture_name, current_confidence, current_metadata))

        # Need full window before making decision
        if len(self.gesture_history) < self.window_size:
            return None

        # Count occurrences of each gesture in window
        gesture_counts: dict[Optional[str], int] = {}
        gesture_confidences: dict[Optional[str], list[float]] = {}
        gesture_metadata: dict[Optional[str], dict] = {}

        for name, conf, meta in self.gesture_history:
            gesture_counts[name] = gesture_counts.get(name, 0) + 1
            if name not in gesture_confidences:
                gesture_confidences[name] = []
                gesture_metadata[name] = meta
            gesture_confidences[name].append(conf)

        # Find most common gesture
        most_common_gesture = max(gesture_counts, key=gesture_counts.get)
        occurrence_ratio = gesture_counts[most_common_gesture] / self.window_size

        # Check if it meets consistency threshold
        if occurrence_ratio >= self.consistency_threshold and most_common_gesture is not None:
            # Update current confirmed gesture
            self.current_gesture = most_common_gesture
            # Average confidence over window
            self.current_confidence = sum(gesture_confidences[most_common_gesture]) / len(
                gesture_confidences[most_common_gesture])

            log_debug(
                f"Gesture confirmed: {self.current_gesture} "
                f"({occurrence_ratio:.1%} consistency, {self.current_confidence:.2f} confidence)"
            )

            return (self.current_gesture, self.current_confidence, gesture_metadata[most_common_gesture])

        # Not consistent enough - no gesture confirmed
        if occurrence_ratio < self.consistency_threshold:
            log_debug(
                f"Gesture inconsistent: {most_common_gesture} "
                f"({occurrence_ratio:.1%} < {self.consistency_threshold:.1%})"
            )

        self.current_gesture = None
        self.current_confidence = 0.0
        return None

    def reset(self) -> None:
        """Reset smoother state (clear history)."""
        self.gesture_history.clear()
        self.current_gesture = None
        self.current_confidence = 0.0

    def get_current_gesture(self) -> Optional[tuple[str, float]]:
        """
        Get currently confirmed gesture without smoothing.

        Returns:
            (gesture_name, confidence) or None
        """
        if self.current_gesture:
            return (self.current_gesture, self.current_confidence)
        return None
