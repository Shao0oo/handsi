"""
Gesture state machine for continuous gesture tracking and debouncing.

Handles:
- Continuous gestures (open_hand for mouse movement)
- Debouncing (prevent rapid re-triggering)
- Hand scale tracking for normalized movement
- Latch state management
"""

import time
from typing import Optional

from handsi.core.types import ActionName
from handsi.core.bus import GestureEvent, RuntimeState
from handsi.core.logging import log_debug


class GestureStateMachine:
    """
    State machine for gesture tracking and debouncing.

    Tracks continuous gestures (like mouse movement) vs discrete gestures (like click).
    Applies debouncing to prevent rapid re-triggering of the same gesture.
    """

    def __init__(
        self,
        runtime_state: RuntimeState,
        debounce_ms: int = 300,
        latch_cooldown_ms: int = 500
    ):
        self.runtime_state = runtime_state
        self.debounce_ms = debounce_ms
        self.latch_cooldown_ms = latch_cooldown_ms

        # Debounce tracking
        self._last_gesture_time: dict[str, float] = {}

        # Latch tracking
        self._last_latch_toggle_time: float = 0.0

        # Continuous gesture state
        self._continuous_gestures = ActionName.continuous_actions()  # Actions that execute without debouncing
        self._current_continuous_gesture: Optional[str] = None

    def should_execute(self, gesture_event: GestureEvent, action_name: ActionName) -> bool:
        """
        Determine if gesture should trigger action execution.

        Applies debouncing for discrete gestures, allows continuous gestures always.
        Checks latch state - only toggle_latch action allowed when latch is off.

        Args:
            gesture_event: The detected gesture
            action_name: The action to execute

        Returns:
            True if action should execute, False if debounced/blocked
        """
        current_time = time.time()
        gesture_name = gesture_event.gesture_name

        # Check latch state
        if not self.is_action_allowed(action_name):
            return False

        # Check if this is a continuous gesture
        if action_name in self._continuous_gestures:
            # Continuous gestures always execute (if latch is active)
            self._current_continuous_gesture = gesture_name
            return True

        # Discrete gesture - apply debouncing
        last_time = self._last_gesture_time.get(gesture_name, 0.0)
        time_since_last = (current_time - last_time) * 1000  # Convert to ms

        if time_since_last < self.debounce_ms:
            log_debug(
                f"Gesture {gesture_name} debounced "
                f"({time_since_last:.0f}ms since last, "
                f"threshold: {self.debounce_ms}ms)"
            )
            return False

        # Allow execution and update timestamp
        self._last_gesture_time[gesture_name] = current_time
        return True

    def update_hand_state(self, metadata: dict) -> None:
        """
        Update hand tracking state in RuntimeState.

        Extracts hand scale and position for mouse movement normalization.
        Handles gesture metadata format (position, hand_scale directly in dict).
        Only updates cursor_position if gesture is from primary hand or is a two-hand gesture.

        Args:
            metadata: Gesture event metadata containing position and hand_scale
        """
        if not metadata:
            return

        with self.runtime_state.lock:
            # Check if this gesture is from primary hand
            gesture_handedness = metadata.get('handedness')
            primary_hand = self.runtime_state.primary_hand

            # Two-hand gestures have special position handling (check for both hand positions)
            is_two_hand = 'left_position' in metadata and 'right_position' in metadata

            # Only update cursor if:
            # 1. Two-hand gesture (uses combined position), OR
            # 2. Gesture is from primary hand
            if not is_two_hand and gesture_handedness != primary_hand:
                log_debug(
                    f"Cursor update skipped: gesture from {gesture_handedness}, "
                    f"primary hand is {primary_hand}"
                )
                return

            # Extract hand_scale and position directly from gesture metadata
            # Gesture detector puts these at the top level
            hand_scale = metadata.get('hand_scale', 0.0)
            position = metadata.get('position', (0.0, 0.0))

            if hand_scale > 0.0:
                self.runtime_state.hand_scale = hand_scale
                self.runtime_state.cursor_position = position

                log_debug(
                    f"Hand state updated: "
                    f"scale={self.runtime_state.hand_scale:.3f}, "
                    f"pos={self.runtime_state.cursor_position}"
                )

    def is_action_allowed(self, action_name: ActionName) -> bool:
        """
        Check if action is allowed based on latch state.

        When latch is OFF: Only enable_latch and alert actions are allowed
        When latch is ON: All actions are allowed

        Args:
            action_name: Name of the action to check

        Returns:
            True if action should execute, False if blocked by latch
        """
        with self.runtime_state.lock:
            latch_active = self.runtime_state.latch_active

        # Always allow these actions regardless of latch state:
        # - ENABLE_LATCH: to re-enable gesture control
        # - Alert actions: habit awareness should work even when gestures disabled
        latch_exempt_actions = {
            ActionName.ENABLE_LATCH,
            ActionName.ALERT_FACIAL_CONTACT,
        }

        if not latch_active and action_name not in latch_exempt_actions:
            log_debug(f"Action {action_name} blocked: latch inactive")
            return False

        return True

    def is_continuous_gesture(self, action_name: ActionName) -> bool:
        """
        Check if action is continuous (vs discrete).

        Args:
            action_name: Name of the action

        Returns:
            True if continuous, False if discrete
        """
        return action_name in self._continuous_gestures

    def reset_debounce(self, gesture_name: str) -> None:
        """
        Reset debounce timer for a specific gesture.

        Args:
            gesture_name: Name of gesture to reset
        """
        if gesture_name in self._last_gesture_time:
            del self._last_gesture_time[gesture_name]
            log_debug(f"Debounce reset for gesture: {gesture_name}")

    def enable_latch(self) -> bool:
        """
        Enable latch state (turn on gesture control).

        Applies cooldown to prevent rapid toggling.

        Returns:
            True if enable succeeded, False if in cooldown or already enabled
        """
        current_time = time.time()
        time_since_last = (current_time - self._last_latch_toggle_time) * 1000  # ms

        # Check cooldown
        if time_since_last < self.latch_cooldown_ms:
            log_debug(
                f"Latch enable blocked by cooldown "
                f"({time_since_last:.0f}ms since last, "
                f"threshold: {self.latch_cooldown_ms}ms)"
            )
            return False

        # Check if already enabled
        with self.runtime_state.lock:
            if self.runtime_state.latch_active:
                log_debug("Latch enable ignored: already active")
                return True  # Not an error, just already on
            self.runtime_state.latch_active = True

        self._last_latch_toggle_time = current_time
        log_debug("Latch ENABLED")
        return True

    def disable_latch(self) -> bool:
        """
        Disable latch state (turn off gesture control).

        Applies cooldown to prevent rapid toggling.

        Returns:
            True if disable succeeded, False if in cooldown or already disabled
        """
        current_time = time.time()
        time_since_last = (current_time - self._last_latch_toggle_time) * 1000  # ms

        # Check cooldown
        if time_since_last < self.latch_cooldown_ms:
            log_debug(
                f"Latch disable blocked by cooldown "
                f"({time_since_last:.0f}ms since last, "
                f"threshold: {self.latch_cooldown_ms}ms)"
            )
            return False

        # Check if already disabled
        with self.runtime_state.lock:
            if not self.runtime_state.latch_active:
                log_debug("Latch disable ignored: already inactive")
                return True  # Not an error, just already off
            self.runtime_state.latch_active = False

        self._last_latch_toggle_time = current_time
        log_debug("Latch DISABLED")
        return True
