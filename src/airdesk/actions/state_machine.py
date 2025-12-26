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

from airdesk.core.bus import GestureEvent, RuntimeState
from airdesk.core.logging import log_debug


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

        # Continuous gesture state
        self._continuous_gestures = {'mouse_move'}  # Actions that are continuous
        self._current_continuous_gesture: Optional[str] = None

    def should_execute(self, gesture_event: GestureEvent, action_name: str) -> bool:
        """
        Determine if gesture should trigger action execution.

        Applies debouncing for discrete gestures, allows continuous gestures always.

        Args:
            gesture_event: The detected gesture
            action_name: The action to execute

        Returns:
            True if action should execute, False if debounced/blocked
        """
        current_time = time.time()
        gesture_name = gesture_event.gesture_name

        # Check if latch is required and active
        # For now, we'll always allow actions (latch feature is Phase 2)

        # Check if this is a continuous gesture
        if action_name in self._continuous_gestures:
            # Continuous gestures always execute
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

        Args:
            metadata: Gesture event metadata containing position and hand_scale
        """
        if not metadata:
            return

        with self.runtime_state.lock:
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

    def is_continuous_gesture(self, action_name: str) -> bool:
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
