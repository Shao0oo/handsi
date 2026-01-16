"""
Volume control action handler.

Handles continuous volume adjustment based on hand movement.
"""

from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.continuous_tracker import ContinuousActionTracker, ContinuousTrackerConfig
from handsi.actions.handlers.base import ContinuousActionHandler
from handsi.core.bus import GestureEvent, RuntimeState
from handsi.core.config import VolumeConfig
from handsi.core.logging import log_debug


class ContinuousVolumeHandler(ContinuousActionHandler):
    """
    Handler for continuous volume control.

    Uses the largest movement vector (horizontal or vertical) to control volume:
    - Right or Up = volume increase
    - Left or Down = volume decrease
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        volume_config: VolumeConfig
    ):
        super().__init__(adapter, runtime_state)
        self.volume_config = volume_config

        # Create tracker with volume config
        tracker_config = ContinuousTrackerConfig(
            dead_zone=volume_config.dead_zone,
            dead_zone_curve=volume_config.dead_zone_curve,
            dead_zone_min_damping=volume_config.dead_zone_min_damping,
            sensitivity=volume_config.sensitivity,
            step_threshold=0.05  # Base threshold before sensitivity adjustment
        )
        self._tracker = ContinuousActionTracker(tracker_config)

    def reset_tracking(self) -> None:
        """Reset volume tracking state."""
        self._tracker.reset()

    def on_gesture_start(self, event: GestureEvent) -> None:
        """Handle volume gesture start."""
        self.reset_tracking()
        log_debug("Volume control started")

    def on_gesture_continue(self, event: GestureEvent) -> None:
        """Handle continuous volume while gesture active."""
        self.execute(event)

    def on_gesture_end(self, event: GestureEvent) -> None:
        """Handle volume gesture end."""
        self.reset_tracking()
        log_debug("Volume control stopped")

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute continuous volume control based on hand movement."""
        # Get hand position and scale
        with self.runtime_state.lock:
            hand_pos = self.runtime_state.cursor_position
            hand_scale = self.runtime_state.hand_scale

        if hand_scale == 0.0:
            log_debug("Volume control skipped: hand_scale=0.0")
            return False

        # Calculate delta from tracker
        delta = self._tracker.update(hand_pos, hand_scale)

        if delta is None:
            # Anchor just initialized
            return True

        # Check if movement is effectively zero
        if abs(delta.dx) < 0.0001 and abs(delta.dy) < 0.0001:
            return True

        # Use LARGEST movement vector (horizontal or vertical)
        # Right/Up = positive (volume increase)
        # Left/Down = negative (volume decrease)
        if abs(delta.dx) > abs(delta.dy):
            # Horizontal movement dominant: right = increase, left = decrease
            movement = delta.dx
            # Apply mirror_x if enabled (for natural camera movement)
            if self.volume_config.mirror_x:
                movement = -movement
        else:
            # Vertical movement dominant: up = increase (negative y), down = decrease
            movement = -delta.dy  # Invert because up is negative in screen coords

        # Check if accumulated movement crosses threshold
        direction = self._tracker.accumulate(movement)

        if direction is not None:
            # Volume changes in increments of 5 (out of 100)
            volume_delta = 5 if direction > 0 else -5

            # Execute volume change
            result = self.adapter.continuous_volume(delta=volume_delta)

            # Update tracker anchor
            self._tracker.update_anchor(hand_pos)

            log_debug(f"Volume step: delta={volume_delta}")
            return result

        return True  # No volume step needed yet
