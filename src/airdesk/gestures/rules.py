"""
Rule-based gesture detection using MediaPipe hand landmarks.

Detects 11 gestures:
- Single hand: index/middle/ring/pinky pinch, fist, open_hand, thumbs_up, swipe_left/right
- Two hands: two_hands_pinch, two_hands_spread, two_hands_close
"""

import time
from collections import deque
from typing import Any, Optional

import numpy as np

from airdesk.core.logging import log_debug


class GestureDetector:
    """
    Rule-based gesture detector using hand landmark geometry.

    Uses MediaPipe hand landmarks (21 points per hand):
    - 0: Wrist
    - 1-4: Thumb (base to tip)
    - 5-8: Index (base to tip)
    - 9-12: Middle (base to tip)
    - 13-16: Ring (base to tip)
    - 17-20: Pinky (base to tip)
    """

    def __init__(
        self,
        pinch_threshold: float = 0.05,
        fist_threshold: float = 0.15,
        open_hand_distance_threshold: float = 0.25,
        open_hand_spread_threshold: float = 0.08,
        swipe_velocity_threshold: float = 0.3,
        confidence_threshold: float = 0.7,
        history_length: int = 10
    ):
        self.pinch_threshold = pinch_threshold
        self.fist_threshold = fist_threshold
        self.open_hand_distance_threshold = open_hand_distance_threshold
        self.open_hand_spread_threshold = open_hand_spread_threshold
        self.swipe_velocity_threshold = swipe_velocity_threshold
        self.confidence_threshold = confidence_threshold

        # History for temporal gestures (swipe, spread, close)
        self.wrist_history: dict[int, deque] = {}  # hand_idx -> deque of (x, y, t)
        self.hand_distance_history = deque(maxlen=history_length)  # two-hand distance
        self.history_length = history_length

    def detect_gestures(self, features: dict[str, Any]) -> list[tuple[str, float, dict]]:
        """
        Detect all gestures from feature vector.

        Args:
            features: Feature dict from extract_features() with 'hands' list

        Returns:
            List of (gesture_name, confidence, metadata) tuples
        """
        gestures = []

        hands = features.get("hands", [])
        if not hands:
            return gestures

        # Single hand gestures
        for hand_idx, hand_data in enumerate(hands):
            landmarks = hand_data.get("landmarks", [])
            if len(landmarks) != 21:
                continue

            # Convert to list of (x, y, z) tuples for easier access
            lm = [(lm["x"], lm["y"], lm["z"]) for lm in landmarks]

            # Check each single-hand gesture
            gesture_checks = [
                self._detect_index_pinch(lm),
                self._detect_middle_pinch(lm),
                self._detect_ring_pinch(lm),
                self._detect_pinky_pinch(lm),
                self._detect_fist(lm),
                self._detect_open_hand(lm),
                self._detect_thumbs_up(lm),
                self._detect_swipe(lm, hand_idx)
            ]

            for result in gesture_checks:
                if result is not None:
                    name, conf, meta = result
                    if conf >= self.confidence_threshold:
                        meta["hand_idx"] = hand_idx
                        meta["handedness"] = hand_data.get("handedness", "unknown")
                        gestures.append((name, conf, meta))

        # Two-hand gestures (require exactly 2 hands)
        if len(hands) == 2:
            lm_left = [(lm["x"], lm["y"], lm["z"]) for lm in hands[0]["landmarks"]]
            lm_right = [(lm["x"], lm["y"], lm["z"]) for lm in hands[1]["landmarks"]]

            two_hand_checks = [
                self._detect_two_hands_pinch(lm_left, lm_right),
                self._detect_two_hands_spread(lm_left, lm_right),
                self._detect_two_hands_close(lm_left, lm_right)
            ]

            for result in two_hand_checks:
                if result is not None:
                    name, conf, meta = result
                    if conf >= self.confidence_threshold:
                        gestures.append((name, conf, meta))

        return gestures

    def _euclidean_distance(self, p1: tuple, p2: tuple) -> float:
        """Calculate Euclidean distance between two 3D points."""
        return np.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))

    # === Single Hand Gestures ===

    def _detect_index_pinch(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect index finger touching thumb tip."""
        thumb_tip = lm[4]
        index_tip = lm[8]
        distance = self._euclidean_distance(thumb_tip, index_tip)

        if distance < self.pinch_threshold:
            confidence = 1.0 - (distance / self.pinch_threshold)
            return ("index_pinch", confidence, {"distance": distance})
        return None

    def _detect_middle_pinch(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect middle finger touching thumb tip."""
        thumb_tip = lm[4]
        middle_tip = lm[12]
        distance = self._euclidean_distance(thumb_tip, middle_tip)

        if distance < self.pinch_threshold:
            confidence = 1.0 - (distance / self.pinch_threshold)
            return ("middle_pinch", confidence, {"distance": distance})
        return None

    def _detect_ring_pinch(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect ring finger touching thumb tip."""
        thumb_tip = lm[4]
        ring_tip = lm[16]
        distance = self._euclidean_distance(thumb_tip, ring_tip)

        if distance < self.pinch_threshold:
            confidence = 1.0 - (distance / self.pinch_threshold)
            return ("ring_pinch", confidence, {"distance": distance})
        return None

    def _detect_pinky_pinch(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect pinky finger touching thumb tip."""
        thumb_tip = lm[4]
        pinky_tip = lm[20]
        distance = self._euclidean_distance(thumb_tip, pinky_tip)

        if distance < self.pinch_threshold:
            confidence = 1.0 - (distance / self.pinch_threshold)
            return ("pinky_pinch", confidence, {"distance": distance})
        return None

    def _detect_fist(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect closed fist (all fingertips close to palm)."""
        wrist = lm[0]
        fingertips = [lm[i] for i in [4, 8, 12, 16, 20]]

        # Calculate average distance from wrist
        avg_distance = np.mean([self._euclidean_distance(tip, wrist) for tip in fingertips])

        if avg_distance < self.fist_threshold:
            confidence = 1.0 - (avg_distance / self.fist_threshold)
            return ("fist", confidence, {"avg_distance": avg_distance})  # type: ignore
        return None

    def _detect_open_hand(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect open hand (fingers extended and spread)."""
        wrist = lm[0]
        fingertips = [lm[i] for i in [4, 8, 12, 16, 20]]

        # Check if fingertips are far from wrist (extended)
        avg_distance = np.mean([self._euclidean_distance(tip, wrist) for tip in fingertips])

        # Check finger spread (distance between adjacent fingertips)
        spreads = [
            self._euclidean_distance(fingertips[i], fingertips[i + 1])
            for i in range(len(fingertips) - 1)
        ]
        avg_spread = np.mean(spreads)

        if (avg_distance > self.open_hand_distance_threshold and
                avg_spread > self.open_hand_spread_threshold):
            # Confidence based on how far fingers are extended and spread
            conf_distance = min(avg_distance / 0.4, 1.0)
            conf_spread = min(avg_spread / 0.15, 1.0)
            confidence = (conf_distance + conf_spread) / 2
            return ("open_hand", confidence, {
                "avg_distance": avg_distance,
                "avg_spread": avg_spread
            })  # type: ignore
        return None

    def _detect_thumbs_up(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect thumbs up (thumb extended upward, other fingers curled)."""
        thumb_tip = lm[4]
        thumb_base = lm[2]
        wrist = lm[0]

        # Check thumb is above base (lower y in image coordinates = higher in real space)
        thumb_extended_up = thumb_tip[1] < thumb_base[1]

        if not thumb_extended_up:
            return None

        # Check other fingers are curled (close to palm)
        other_fingertips = [lm[i] for i in [8, 12, 16, 20]]
        avg_curl = np.mean([self._euclidean_distance(tip, wrist) for tip in other_fingertips])

        curl_threshold = 0.2
        if avg_curl < curl_threshold:
            confidence = 1.0 - (avg_curl / curl_threshold)
            return ("thumbs_up", confidence, {"avg_curl": avg_curl})  # type: ignore
        return None

    def _detect_swipe(self, lm: list, hand_idx: int) -> Optional[tuple[str, float, dict]]:
        """Detect horizontal swipe (left/right) based on wrist movement."""
        wrist = lm[0]
        current_time = time.time()

        # Initialize history for this hand if needed
        if hand_idx not in self.wrist_history:
            self.wrist_history[hand_idx] = deque(maxlen=self.history_length)

        # Add current position
        self.wrist_history[hand_idx].append((wrist[0], wrist[1], current_time))

        # Need enough history to detect swipe
        if len(self.wrist_history[hand_idx]) < 5:
            return None

        history = list(self.wrist_history[hand_idx])

        # Calculate horizontal velocity
        dx = history[-1][0] - history[0][0]
        dt = history[-1][2] - history[0][2]

        if dt <= 0:
            return None

        velocity_x = dx / dt

        # Check if velocity exceeds threshold
        if abs(velocity_x) > self.swipe_velocity_threshold:
            if velocity_x > 0:
                confidence = min(abs(velocity_x) / 1.0, 1.0)
                return ("swipe_right", confidence, {"velocity": velocity_x})
            else:
                confidence = min(abs(velocity_x) / 1.0, 1.0)
                return ("swipe_left", confidence, {"velocity": velocity_x})

        return None

    # === Two Hand Gestures ===

    def _detect_two_hands_pinch(self, lm_left: list, lm_right: list) -> Optional[tuple[str, float, dict]]:
        """Detect both hands making index pinch."""
        left_pinch = self._detect_index_pinch(lm_left)
        right_pinch = self._detect_index_pinch(lm_right)

        if left_pinch and right_pinch:
            confidence = (left_pinch[1] + right_pinch[1]) / 2
            return ("two_hands_pinch", confidence, {
                "left_conf": left_pinch[1],
                "right_conf": right_pinch[1]
            })
        return None

    def _detect_two_hands_spread(self, lm_left: list, lm_right: list) -> Optional[tuple[str, float, dict]]:
        """Detect two hands moving apart (spread gesture)."""
        left_wrist = lm_left[0]
        right_wrist = lm_right[0]
        distance = self._euclidean_distance(left_wrist, right_wrist)

        current_time = time.time()
        self.hand_distance_history.append((distance, current_time))

        # Need history to detect movement
        if len(self.hand_distance_history) < 5:
            return None

        history = list(self.hand_distance_history)

        # Calculate velocity (distance change over time)
        d_distance = history[-1][0] - history[0][0]
        dt = history[-1][1] - history[0][1]

        if dt <= 0:
            return None

        velocity = d_distance / dt

        # Positive velocity = spreading apart
        spread_threshold = 0.2
        if velocity > spread_threshold:
            confidence = min(velocity / 1.0, 1.0)
            return ("two_hands_spread", confidence, {
                "velocity": velocity,
                "distance": distance
            })

        return None

    def _detect_two_hands_close(self, lm_left: list, lm_right: list) -> Optional[tuple[str, float, dict]]:
        """Detect two hands moving together (close gesture)."""
        left_wrist = lm_left[0]
        right_wrist = lm_right[0]
        distance = self._euclidean_distance(left_wrist, right_wrist)

        current_time = time.time()
        self.hand_distance_history.append((distance, current_time))

        # Need history to detect movement
        if len(self.hand_distance_history) < 5:
            return None

        history = list(self.hand_distance_history)

        # Calculate velocity (distance change over time)
        d_distance = history[-1][0] - history[0][0]
        dt = history[-1][1] - history[0][1]

        if dt <= 0:
            return None

        velocity = d_distance / dt

        # Negative velocity = closing together
        close_threshold = -0.2
        if velocity < close_threshold:
            confidence = min(abs(velocity) / 1.0, 1.0)
            return ("two_hands_close", confidence, {
                "velocity": velocity,
                "distance": distance
            })

        return None
