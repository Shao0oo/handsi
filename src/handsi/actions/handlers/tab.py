"""
Tab switching action handler.

Handles continuous tab switching based on hand movement.
"""

from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.continuous_tracker import ContinuousActionTracker, ContinuousTrackerConfig
from handsi.actions.handlers.base import ContinuousActionHandler
from handsi.core.bus import GestureEvent, RuntimeState
from handsi.core.config import TabConfig
from handsi.core.logging import log_debug


class ContinuousTabHandler(ContinuousActionHandler):
    """
    Handler for continuous tab switching.

    Uses the largest movement vector (horizontal or vertical) to control tabs:
    - Right or Up = next tab (Ctrl+Tab)
    - Left or Down = previous tab (Ctrl+Shift+Tab)
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        tab_config: TabConfig
    ):
        super().__init__(adapter, runtime_state)
        self.tab_config = tab_config

        # Create tracker with tab config
        tracker_config = ContinuousTrackerConfig(
            dead_zone=tab_config.dead_zone,
            dead_zone_curve=tab_config.dead_zone_curve,
            dead_zone_min_damping=tab_config.dead_zone_min_damping,
            sensitivity=tab_config.sensitivity,
            step_threshold=0.05  # Base threshold before sensitivity adjustment
        )
        self._tracker = ContinuousActionTracker(tracker_config)

    def reset_tracking(self) -> None:
        """Reset tab tracking state."""
        self._tracker.reset()

    def on_gesture_start(self, event: GestureEvent) -> None:
        """Handle tab gesture start."""
        self.reset_tracking()
        log_debug("Tab control started")

    def on_gesture_continue(self, event: GestureEvent) -> None:
        """Handle continuous tab switching while gesture active."""
        self.execute(event)

    def on_gesture_end(self, event: GestureEvent) -> None:
        """Handle tab gesture end."""
        self.reset_tracking()
        log_debug("Tab control stopped")

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute continuous tab switching based on hand movement."""
        # Get hand position and scale
        with self.runtime_state.lock:
            hand_pos = self.runtime_state.cursor_position
            hand_scale = self.runtime_state.hand_scale

        if hand_scale == 0.0:
            log_debug("Tab control skipped: hand_scale=0.0")
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
        # Left/Up = positive (next tab)
        # Right/Down = negative (previous tab)
        # Note: Horizontal is inverted because camera mirrors the view
        if abs(delta.dx) > abs(delta.dy):
            # Horizontal movement dominant: left = next, right = prev (inverted for camera mirror)
            movement = -delta.dx
        else:
            # Vertical movement dominant: up = next (negative y), down = prev
            movement = -delta.dy  # Invert because up is negative in screen coords

        # Check if accumulated movement crosses threshold
        direction = self._tracker.accumulate(movement)

        if direction is not None:
            # Execute tab switch
            result = self.adapter.continuous_tab(direction=direction)

            # Update tracker anchor
            self._tracker.update_anchor(hand_pos)

            log_debug(f"Tab switch: direction={direction}")
            return result

        return True  # No tab switch needed yet
