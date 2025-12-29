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

from handsi.core.logging import log_debug


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
        swipe_velocity_threshold: float = 0.5,
        thumbs_vertical_threshold: float = 1.3,
        confidence_threshold: float = 0.7,
        history_length: int = 10
    ):
        self.pinch_threshold = pinch_threshold
        self.fist_threshold = fist_threshold
        self.open_hand_distance_threshold = open_hand_distance_threshold
        self.open_hand_spread_threshold = open_hand_spread_threshold
        self.swipe_velocity_threshold = swipe_velocity_threshold
        self.thumbs_vertical_threshold = thumbs_vertical_threshold
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
                self._detect_two_finger_pinch(lm),
                self._detect_middle_pinch(lm),
                self._detect_ring_pinch(lm),
                self._detect_pinky_pinch(lm),
                self._detect_fist(lm),
                self._detect_open_hand(lm),
                self._detect_thumbs_up(lm),
                self._detect_thumbs_down(lm),
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
                self._detect_two_hands_open(lm_left, lm_right),
                # TODO: Implement spread detection using _detect_swipe
                # self._detect_two_hands_spread(lm_left, lm_right), 
                # self._detect_two_hands_close(lm_left, lm_right)
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

    def _get_hand_scale(self, lm: list) -> float:
        """
        Calculate hand scale (size reference) for normalizing distances.

        Uses the distance from wrist to middle finger MCP as the base unit.
        This makes all distance measurements relative to hand size, allowing
        gestures to work consistently regardless of distance from camera.

        Args:
            lm: List of landmarks

        Returns:
            Hand scale (distance from wrist to middle MCP), or 1.0 if invalid
        """
        wrist = lm[0]
        middle_mcp = lm[9]  # Middle finger MCP (base knuckle)

        hand_scale = self._euclidean_distance(wrist, middle_mcp)

        # Avoid division by zero - return 1.0 as fallback
        if hand_scale < 0.01:
            return 1.0

        return hand_scale

    def _normalized_distance(self, p1: tuple, p2: tuple, hand_scale: float) -> float:
        """
        Calculate distance normalized by hand scale.

        This makes distance measurements scale-invariant - a pinch gesture
        will have the same normalized distance whether the hand is close
        to or far from the camera.

        Args:
            p1: First point
            p2: Second point
            hand_scale: Hand size reference (from _get_hand_scale)

        Returns:
            Distance as fraction of hand size
        """
        distance = self._euclidean_distance(p1, p2)
        return distance / hand_scale
    
    def _get_hand_center_of_mass(self, lm: list) -> tuple[float, float]:
        """
        Calculate hand center of mass (average of all 21 landmarks).

        Returns 2D position (x, y) in normalized screen coordinates (0-1 range).

        Args:
            lm: List of landmarks [(x, y, z), ...]

        Returns:
            (x, y) tuple representing center of mass in raw screen coordinates
        """
        x_coords = [p[0] for p in lm]
        y_coords = [p[1] for p in lm]

        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)

        return (center_x, center_y)

    def _is_finger_extended(self, lm: list, finger_tip_idx: int, finger_mcp_idx: int,
                           extension_ratio: float = 1.3) -> bool:
        """
        Check if a finger is extended (straight).

        A finger is considered extended if the distance from fingertip to wrist
        is significantly greater than the distance from MCP knuckle to wrist.

        Args:
            lm: List of landmarks
            finger_tip_idx: Index of fingertip landmark
            finger_mcp_idx: Index of MCP (knuckle) landmark
            extension_ratio: Minimum ratio of tip:mcp distance (default 1.3)

        Returns:
            True if finger is extended, False otherwise
        """
        wrist = lm[0]
        tip = lm[finger_tip_idx]
        mcp = lm[finger_mcp_idx]

        tip_distance = self._euclidean_distance(tip, wrist)
        mcp_distance = self._euclidean_distance(mcp, wrist)

        # Avoid division by zero
        if mcp_distance < 0.01:
            return False

        ratio = tip_distance / mcp_distance
        return ratio >= extension_ratio

    def _is_finger_closed(self, lm: list, finger_tip_idx: int, finger_mcp_idx: int,
                         curl_ratio: float = 1.1) -> bool:
        """
        Check if a finger is closed (curled).

        A finger is considered closed if the distance from fingertip to wrist
        is close to the distance from MCP knuckle to wrist.

        Args:
            lm: List of landmarks
            finger_tip_idx: Index of fingertip landmark
            finger_mcp_idx: Index of MCP (knuckle) landmark
            curl_ratio: Maximum ratio of tip:mcp distance for closed finger (default 1.1)

        Returns:
            True if finger is closed, False otherwise
        """
        # Special handling for thumb (different geometry)
        if finger_tip_idx == 4:
            return self._is_thumb_closed(lm)

        wrist = lm[0]
        tip = lm[finger_tip_idx]
        mcp = lm[finger_mcp_idx]

        tip_distance = self._euclidean_distance(tip, wrist)
        mcp_distance = self._euclidean_distance(mcp, wrist)

        # Avoid division by zero
        if mcp_distance < 0.01:
            return True  # Default to closed if too close to wrist

        ratio = tip_distance / mcp_distance
        return ratio <= curl_ratio

    def _is_thumb_closed(self, lm: list) -> bool:
        """
        Check if thumb is closed (curled across palm).

        Thumb has different geometry - when closed, it curls across the palm
        toward the fingers.

        Args:
            lm: List of landmarks

        Returns:
            True if thumb is closed, False otherwise
        """
        thumb_tip = lm[4]
        index_mcp = lm[5]  # Index finger base (thumb curls toward this)

        # Get hand scale for normalization
        hand_scale = self._get_hand_scale(lm)

        # Check if thumb tip is close to index MCP (palm area)
        dist_to_index_mcp = self._normalized_distance(thumb_tip, index_mcp, hand_scale)

        # Thumb is closed if tip is within 50% of hand size from index MCP
        return dist_to_index_mcp < 0.5

    # === Single Hand Gestures ===

    def _detect_index_pinch(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect index finger touching thumb tip (other fingers extended)."""
        # Get hand scale for normalization
        hand_scale = self._get_hand_scale(lm)

        # Calculate normalized distance
        thumb_tip = lm[4]
        index_tip = lm[8]
        distance = self._normalized_distance(thumb_tip, index_tip, hand_scale)

        if distance >= self.pinch_threshold:
            return None

        # Check that other fingers (middle, ring, pinky) are extended
        other_fingers = [(12, 9), (16, 13), (20, 17)]  # (tip, mcp)
        extended_count = sum(1 for tip, mcp in other_fingers
                            if self._is_finger_extended(lm, tip, mcp))

        # Require at least 2 of 3 other fingers to be extended
        if extended_count < 3:
            return None

        confidence = 1.0 - distance
        # position = self._get_hand_center_of_mass(lm)

        return ("index_pinch", confidence, {
            "distance": distance,
            "extended_count": extended_count,
            "position": lm[0],
            "hand_scale": hand_scale
        })

    def _detect_two_finger_pinch(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect index and middle finger touching thumb tip (other fingers extended)."""
        # Get hand scale for normalization
        hand_scale = self._get_hand_scale(lm)

        # Calculate normalized distance
        thumb_tip = lm[4]
        index_tip = lm[8]
        middle_tip = lm[12]
        index_distance = self._normalized_distance(thumb_tip, index_tip, hand_scale)
        middle_distance = self._normalized_distance(thumb_tip, middle_tip, hand_scale)
        distance = (index_distance + middle_distance) / 3 # Boost two finger confidence

        if index_distance >= self.pinch_threshold or middle_distance >= self.pinch_threshold:
            return None

        # Check that other fingers (middle, ring, pinky) are extended
        other_fingers = [(16, 13), (20, 17)]  # (tip, mcp)
        extended_count = sum(1 for tip, mcp in other_fingers
                            if self._is_finger_extended(lm, tip, mcp))

        # # Don't require extension. Fingers tend to close when pinching two fingers.
        if extended_count < 1:
            return None

        confidence = (1 - (index_distance + middle_distance)/2)
        # # position = self._get_hand_center_of_mass(lm)

        return ("two_finger_pinch", confidence, {
            "distance": distance,
            "extended_count": extended_count,
            "position": lm[0],
            "hand_scale": hand_scale
        })

    def _detect_middle_pinch(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect middle finger touching thumb tip (other fingers extended)."""
        # Get hand scale for normalization
        hand_scale = self._get_hand_scale(lm)

        # Calculate normalized distance
        thumb_tip = lm[4]
        middle_tip = lm[12]
        distance = self._normalized_distance(thumb_tip, middle_tip, hand_scale)

        if distance >= self.pinch_threshold:
            return None

        # Check that other fingers (index, ring, pinky) are extended
        other_fingers = [(8, 5), (16, 13), (20, 17)]  # (tip, mcp)
        extended_count = sum(1 for tip, mcp in other_fingers
                            if self._is_finger_extended(lm, tip, mcp))

        # Require at least 2 of 3 other fingers to be extended
        if extended_count < 3:
            return None

        confidence = 1.0 - distance
        # # position = self._get_hand_center_of_mass(lm)

        return ("middle_pinch", confidence, {
            "distance": distance,
            "extended_count": extended_count,
            "position": lm[0],
            "hand_scale": hand_scale
        })

    def _detect_ring_pinch(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect ring finger touching thumb tip (other fingers extended)."""
        # Get hand scale for normalization
        hand_scale = self._get_hand_scale(lm)

        # Calculate normalized distance
        thumb_tip = lm[4]
        ring_tip = lm[16]
        distance = self._normalized_distance(thumb_tip, ring_tip, hand_scale)

        if distance >= self.pinch_threshold:
            return None

        # Check that other fingers (index, middle, pinky) are extended
        other_fingers = [(8, 5), (12, 9), (20, 17)]  # (tip, mcp)
        extended_count = sum(1 for tip, mcp in other_fingers
                            if self._is_finger_extended(lm, tip, mcp))

        # Require at least 2 of 3 other fingers to be extended
        if extended_count < 2:
            return None

        confidence = 1.0 - distance
        # # position = self._get_hand_center_of_mass(lm)

        return ("ring_pinch", confidence, {
            "distance": distance,
            "extended_count": extended_count,
            "position": lm[0],
            "hand_scale": hand_scale
        })

    def _detect_pinky_pinch(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect pinky finger touching thumb tip (other fingers extended)."""
        # Get hand scale for normalization
        hand_scale = self._get_hand_scale(lm)

        # Calculate normalized distance
        thumb_tip = lm[4]
        pinky_tip = lm[20]
        distance = self._normalized_distance(thumb_tip, pinky_tip, hand_scale)

        if distance >= self.pinch_threshold:
            return None

        # Check that other fingers (index, middle, ring) are extended
        other_fingers = [(8, 5), (12, 9), (16, 13)]  # (tip, mcp)
        extended_count = sum(1 for tip, mcp in other_fingers
                            if self._is_finger_extended(lm, tip, mcp))

        # Require at least 2 of 3 other fingers to be extended
        if extended_count < 2:
            return None

        confidence = 1.0 - distance
        # # position = self._get_hand_center_of_mass(lm)

        return ("pinky_pinch", confidence, {
            "distance": distance,
            "extended_count": extended_count,
            "position": lm[0],
            "hand_scale": hand_scale
        })

    def _detect_fist(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect closed fist (all fingers curled/closed)."""
        # Get hand scale for normalization
        hand_scale = self._get_hand_scale(lm)

        # Check if ALL fingers are closed (using correct joints)
        fingers = [
            (4, 1),   # Thumb (tip to CMC, not MCP)
            (8, 5),   # Index
            (12, 9),  # Middle
            (16, 13), # Ring
            (20, 17)  # Pinky
        ]

        closed_count = 0
        for tip_idx, mcp_idx in fingers:
            # Use slightly looser curl ratio for fist detection (allow 20% extension)
            if self._is_finger_closed(lm, tip_idx, mcp_idx, curl_ratio=1.2):
                closed_count += 1

        # Require at least 4 of 5 fingers to be closed
        if closed_count < 5:
            return None

        # Calculate confidence based on how closed the fingers are
        # Since we already validated with ratio checks, just return high confidence
        confidence = min(closed_count / 5.0, 1.0)
        # # position = self._get_hand_center_of_mass(lm)

        return ("fist", confidence, {
            "closed_count": closed_count,
            "position": lm[0],
            "hand_scale": hand_scale
        })

    def _detect_open_hand(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect open hand (all 5 fingers fully extended and spread)."""
        # Get hand scale for normalization
        hand_scale = self._get_hand_scale(lm)

        # Check if ALL fingers are extended
        # Finger landmarks: (tip, mcp)
        fingers = [
            (4, 2),   # Thumb (tip, base - using CMC instead of MCP)
            (8, 5),   # Index
            (12, 9),  # Middle
            (16, 13), # Ring
            (20, 17)  # Pinky
        ]

        # All fingers must be extended
        extended_count = 0
        for tip_idx, mcp_idx in fingers:
            if self._is_finger_extended(lm, tip_idx, mcp_idx):
                extended_count += 1

        # Require all 5 fingers to be extended
        if extended_count < 5:
            # print(f"Open hand: only {extended_count} fingers extended, need 5")
            return None

        # Secondary checks: normalized finger spread
        fingertips = [lm[i] for i in [4, 8, 12, 16, 20]]
        spreads = [
            self._normalized_distance(fingertips[i], fingertips[i + 1], hand_scale)
            for i in range(len(fingertips) - 1)
        ]
        spreads_thumb = [
            self._normalized_distance(fingertips[0], fingertips[i+1], hand_scale)
            for i in range(len(fingertips) - 1)
        ]
        avg_spread = np.mean(spreads)
        min_spread = np.min(spreads_thumb)

        # Check minimum spread
        if avg_spread < self.open_hand_spread_threshold:
            # print(f"Open hand average spread too small: {avg_spread:.3f} < {self.open_hand_spread_threshold:.3f}")
            return None
        if min_spread < self.open_hand_distance_threshold:
            # print(f"Open hand spread too small: {min_spread:.3f} < {self.open_hand_distance_threshold:.3f}")
            return None

        # Calculate confidence based on spread
        conf_spread = min(avg_spread / 0.5, 1.0)
        # print(f"Open hand detected with average spread {avg_spread:.3f}, confidence {conf_spread:.2f}")
        confidence = conf_spread
        # # position = self._get_hand_center_of_mass(lm)

        return ("open_hand", confidence, {
            "extended_count": extended_count,
            "avg_spread": avg_spread,
            "position": lm[0],
            "hand_scale": hand_scale
        }) # type: ignore

    def _detect_thumbs_up(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect thumbs up (thumb extended upward, other fingers curled)."""
        # Get hand scale for normalization
        hand_scale = self._get_hand_scale(lm)

        thumb_tip = lm[4]
        thumb_base = lm[2]
        wrist = lm[0]

        # Check thumb is extended
        if not self._is_finger_extended(lm, 4, 2, extension_ratio=1.5):
            return None

        # Check thumb is pointing upward (lower y = higher in image space)
        # Normalize the vertical threshold by hand scale
        vertical_threshold = self.thumbs_vertical_threshold * hand_scale
        thumb_vertical = thumb_tip[1] < wrist[1] - vertical_threshold

        if not thumb_vertical:
            return None

        # Check other 4 fingers are closed
        other_fingers = [(8, 5), (12, 9), (16, 13), (20, 17)]  # (tip, mcp)
        closed_count = sum(1 for tip, mcp in other_fingers
                          if self._is_finger_closed(lm, tip, mcp))

        # Require at least 3 of 4 fingers to be closed
        if closed_count < 4:
            return None

        # Calculate normalized vertical distance
        vertical_distance = (wrist[1] - thumb_tip[1]) / hand_scale
        confidence = min(vertical_distance / 0.5, 1.0)
        # # position = self._get_hand_center_of_mass(lm)

        return ("thumbs_up", confidence, {
            "vertical_distance": vertical_distance,
            "closed_count": closed_count,
            "position": lm[0],
            "hand_scale": hand_scale
        })
    
    def _detect_thumbs_down(self, lm: list) -> Optional[tuple[str, float, dict]]:
        """Detect thumbs down (thumb extended downwards, other fingers curled)."""
        # Get hand scale for normalization
        hand_scale = self._get_hand_scale(lm)

        thumb_tip = lm[4]
        thumb_base = lm[2]
        wrist = lm[0]

        # Check thumb is extended
        if not self._is_finger_extended(lm, 4, 2, extension_ratio=1.5):
            return None

        # Check thumb is pointing downwards (higher y = lower in image space)
        # Normalize the vertical threshold by hand scale
        vertical_threshold = self.thumbs_vertical_threshold * hand_scale
        thumb_vertical = thumb_tip[1] > wrist[1] + vertical_threshold

        if not thumb_vertical:
            return None

        # Check other 4 fingers are closed
        other_fingers = [(8, 5), (12, 9), (16, 13), (20, 17)]  # (tip, mcp)
        closed_count = sum(1 for tip, mcp in other_fingers
                          if self._is_finger_closed(lm, tip, mcp))

        # Require at least all four fingers to be closed
        if closed_count < 4:
            return None

        # Calculate normalized vertical distance
        vertical_distance = (wrist[1] + thumb_tip[1]) / hand_scale
        confidence = min(vertical_distance / 0.5, 1.0)
        # # position = self._get_hand_center_of_mass(lm)

        return ("thumbs_down", confidence, {
            "vertical_distance": vertical_distance,
            "closed_count": closed_count,
            "position": lm[0],
            "hand_scale": hand_scale
        })

    def _detect_swipe(self, lm: list, hand_idx: int) -> Optional[tuple[str, float, dict]]:
        """
        Detect swipe (left/right/up/down) with open hand.

        Swipe requires an open hand as prerequisite. If detected, swipe takes
        precedence over open_hand to avoid competing detections.
        """
        # PREREQUISITE: Check if hand is open
        open_hand_result = self._detect_open_hand(lm)
        if open_hand_result is None:
            return None  # Hand is not open, cannot swipe

        # Get hand scale for normalization
        hand_scale = self._get_hand_scale(lm)

        wrist = lm[0]
        current_time = time.time()

        # Initialize history for this hand if needed
        if hand_idx not in self.wrist_history:
            self.wrist_history[hand_idx] = deque(maxlen=self.history_length)

        # Add current position with hand scale
        self.wrist_history[hand_idx].append((wrist[0], wrist[1], current_time, hand_scale))

        # Need enough history to detect swipe
        if len(self.wrist_history[hand_idx]) < 3:
            print("Not enough history to detect swipe")
            return open_hand_result

        history = list(self.wrist_history[hand_idx])

        # Calculate average velocity over last 3 frames
        n = min(3, len(history))
        dx = sum(history[i][0] - history[i-1][0] for i in range(-n+1, 0)) if n > 1 else 0
        dy = sum(history[i][1] - history[i-1][1] for i in range(-n+1, 0)) if n > 1 else 0
        dt = history[-1][2] - history[-n][2]
        avg_hand_scale = sum(h[3] for h in history[-n:]) / n

        if dt <= 0 or avg_hand_scale < 0.01:
            print("Invalid swipe history - no movement detected")
            return open_hand_result

        # Normalize velocities by hand scale
        velocity_x = (dx / dt) / avg_hand_scale
        velocity_y = (dy / dt) / avg_hand_scale

        # Determine dominant direction (horizontal vs vertical)
        abs_vx = abs(velocity_x)
        abs_vy = abs(velocity_y)

        # print(f"Hand scale: {avg_hand_scale}, Swipe velocity thresholds {self.swipe_velocity_threshold}, vx={abs_vx:.3f}, vy={abs_vy:.3f},")

        # Check if velocity exceeds threshold
        if abs_vx > self.swipe_velocity_threshold or abs_vy > self.swipe_velocity_threshold:
            # Return the dominant direction
            if abs_vx > abs_vy:
                # Horizontal swipe (left/right)
                # # position = self._get_hand_center_of_mass(lm)
                hand_scale = self._get_hand_scale(lm)
                if velocity_x > 0:
                    confidence = min(abs_vx * 5, 1.0)  # TODO: tune this multiplier
                    return ("swipe_right", confidence, {
                        "velocity_x": velocity_x,
                        "velocity_y": velocity_y,
                        "position": lm[0],
                        "hand_scale": hand_scale
                    })
                else:
                    confidence = min(abs_vx * 5, 1.0)  # TODO: tune this multiplier
                    return ("swipe_left", confidence, {
                        "velocity_x": velocity_x,
                        "velocity_y": velocity_y,
                        "position": lm[0],
                        "hand_scale": hand_scale
                    })
            else:
                # Vertical swipe (up/down)
                # Note: in image coordinates, lower y = higher in real space
                # # position = self._get_hand_center_of_mass(lm)
                hand_scale = self._get_hand_scale(lm)
                if velocity_y < 0:
                    confidence = min(abs_vy * 5, 1.0)
                    # print(f"Swipe up detected with confidence {confidence:.2f}")
                    return ("swipe_up", confidence, {
                        "velocity_x": velocity_x,
                        "velocity_y": velocity_y,
                        "position": lm[0],
                        "hand_scale": hand_scale
                    })
                else:
                    confidence = min(abs_vy * 5, 1.0)
                    # print(f"Swipe down detected with confidence {confidence:.2f}")
                    return ("swipe_down", confidence, {
                        "velocity_x": velocity_x,
                        "velocity_y": velocity_y,
                        "position": lm[0],
                        "hand_scale": hand_scale
                    })

        # No swipe detected, but hand is open - return None so open_hand can fire
        return open_hand_result

    # === Two Hand Gestures ===

    def _detect_two_hands_open(self, lm_left: list, lm_right: list) -> Optional[tuple[str, float, dict]]:
        """Detect both hands making open hand."""
        left_open = self._detect_open_hand(lm_left)
        right_open = self._detect_open_hand(lm_right)

        if left_open and right_open:
            confidence = (left_open[1] + right_open[1]) / 2.0 + 0.1  # Boost confidence slightly
            left_position = self._get_hand_center_of_mass(lm_left)
            right_position = self._get_hand_center_of_mass(lm_right)

            # Average hand scale for two hands
            left_scale = self._get_hand_scale(lm_left)
            right_scale = self._get_hand_scale(lm_right)
            avg_hand_scale = (left_scale + right_scale) / 2.0

            return ("two_hands_open", confidence, {
                "left_conf": left_open[1],
                "right_conf": right_open[1],
                "left_position": left_position,
                "right_position": right_position,
                "hand_scale": avg_hand_scale
            })
        return None
    
    def _detect_two_hands_pinch(self, lm_left: list, lm_right: list) -> Optional[tuple[str, float, dict]]:
        """Detect both hands making index pinch."""
        left_pinch = self._detect_index_pinch(lm_left)
        right_pinch = self._detect_index_pinch(lm_right)

        if left_pinch and right_pinch:
            confidence = (left_pinch[1] + right_pinch[1]) / 2.0 + 0.1  # Boost confidence slightly
            left_position = self._get_hand_center_of_mass(lm_left)
            right_position = self._get_hand_center_of_mass(lm_right)

            # Average hand scale for two hands
            left_scale = self._get_hand_scale(lm_left)
            right_scale = self._get_hand_scale(lm_right)
            avg_hand_scale = (left_scale + right_scale) / 2.0

            return ("two_hands_pinch", confidence, {
                "left_conf": left_pinch[1],
                "right_conf": right_pinch[1],
                "left_position": left_position,
                "right_position": right_position,
                "hand_scale": avg_hand_scale
            })
        return None

    def _detect_two_hands_spread(self, lm_left: list, lm_right: list) -> Optional[tuple[str, float, dict]]:
        """Detect two hands moving apart (spread gesture)."""
        # Get hand scales for normalization (average both hands)
        left_scale = self._get_hand_scale(lm_left)
        right_scale = self._get_hand_scale(lm_right)
        avg_hand_scale = (left_scale + right_scale) / 2

        left_wrist = lm_left[0]
        right_wrist = lm_right[0]
        distance = self._normalized_distance(left_wrist, right_wrist, avg_hand_scale)

        current_time = time.time()
        self.hand_distance_history.append((distance, current_time, avg_hand_scale))

        # Need history to detect movement
        if len(self.hand_distance_history) < 5:
            return None

        history = list(self.hand_distance_history)

        # Calculate normalized velocity (distance change over time)
        d_distance = history[-1][0] - history[0][0]
        dt = history[-1][1] - history[0][1]

        if dt <= 0:
            return None

        velocity = d_distance / dt

        # Positive velocity = spreading apart (threshold now in hand-relative units)
        spread_threshold = 0.5  # 50% of hand size per second
        if velocity > spread_threshold:
            confidence = min(velocity / 2.0, 1.0)
            left_position = self._get_hand_center_of_mass(lm_left)
            right_position = self._get_hand_center_of_mass(lm_right)

            return ("two_hands_spread", confidence, {
                "velocity": velocity,
                "distance": distance,
                "left_position": left_position,
                "right_position": right_position,
                "hand_scale": avg_hand_scale
            })

        return None

    def _detect_two_hands_close(self, lm_left: list, lm_right: list) -> Optional[tuple[str, float, dict]]:
        """Detect two hands moving together (close gesture)."""
        # Get hand scales for normalization (average both hands)
        left_scale = self._get_hand_scale(lm_left)
        right_scale = self._get_hand_scale(lm_right)
        avg_hand_scale = (left_scale + right_scale) / 2

        left_wrist = lm_left[0]
        right_wrist = lm_right[0]
        distance = self._normalized_distance(left_wrist, right_wrist, avg_hand_scale)

        current_time = time.time()
        self.hand_distance_history.append((distance, current_time, avg_hand_scale))

        # Need history to detect movement
        if len(self.hand_distance_history) < 5:
            return None

        history = list(self.hand_distance_history)

        # Calculate normalized velocity (distance change over time)
        d_distance = history[-1][0] - history[0][0]
        dt = history[-1][1] - history[0][1]

        if dt <= 0:
            return None

        velocity = d_distance / dt

        # Negative velocity = closing together (threshold now in hand-relative units)
        close_threshold = -0.5  # -50% of hand size per second
        if velocity < close_threshold:
            confidence = min(abs(velocity) / 2.0, 1.0)
            left_position = self._get_hand_center_of_mass(lm_left)
            right_position = self._get_hand_center_of_mass(lm_right)

            return ("two_hands_close", confidence, {
                "velocity": velocity,
                "distance": distance,
                "left_position": left_position,
                "right_position": right_position,
                "hand_scale": avg_hand_scale
            })

        return None
