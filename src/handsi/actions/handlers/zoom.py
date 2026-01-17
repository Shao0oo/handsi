"""
Zoom action handlers.

Handles both discrete zoom steps and continuous zoom tracking.
"""

from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.continuous_tracker import ContinuousActionTracker, ContinuousTrackerConfig
from handsi.actions.handlers.base import ContinuousActionHandler, DiscreteActionHandler
from handsi.core.bus import GestureEvent, RuntimeState
from handsi.core.config import ZoomConfig
from handsi.core.logging import log_debug, log_info


class ZoomStepHandler(DiscreteActionHandler):
    """
    Handler for discrete zoom steps (zoom_in, zoom_out).

    Executes a single zoom step in the specified direction.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        zoom_config: ZoomConfig,
        direction: str  # 'in' or 'out'
    ):
        super().__init__(adapter, runtime_state)
        self.zoom_config = zoom_config
        self.direction = direction

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute a single zoom step."""
        zoom_step = self.zoom_config.zoom_step
        return self.adapter.zoom(direction=self.direction, step=zoom_step)


class ContinuousZoomHandler(ContinuousActionHandler):
    """
    Handler for continuous zoom tracking.

    Tracks hand vertical movement and triggers zoom steps (Cmd+Plus/Minus)
    when movement crosses thresholds.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        zoom_config: ZoomConfig
    ):
        super().__init__(adapter, runtime_state)
        self.zoom_config = zoom_config

        # Create tracker with zoom config
        tracker_config = ContinuousTrackerConfig(
            dead_zone=zoom_config.dead_zone,
            dead_zone_curve=zoom_config.dead_zone_curve,
            dead_zone_min_damping=zoom_config.dead_zone_min_damping,
            sensitivity=zoom_config.sensitivity,
            step_threshold=0.05  # Base threshold before sensitivity adjustment
        )
        self._tracker = ContinuousActionTracker(tracker_config)

    def reset_tracking(self) -> None:
        """Reset zoom tracking state."""
        self._tracker.reset()

    def on_gesture_start(self, event: GestureEvent) -> None:
        """Handle zoom gesture start."""
        self.reset_tracking()
        log_debug("Zoom tracking started")

    def on_gesture_continue(self, event: GestureEvent) -> None:
        """Handle continuous zoom while gesture active."""
        self.execute(event)

    def on_gesture_end(self, event: GestureEvent) -> None:
        """Handle zoom gesture end."""
        self.reset_tracking()
        log_debug("Zoom tracking stopped")

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute continuous zoom based on hand movement."""
        # Get hand position and scale
        with self.runtime_state.lock:
            hand_pos = self.runtime_state.cursor_position
            hand_scale = self.runtime_state.hand_scale

        if hand_scale == 0.0:
            log_debug("Zoom skipped: hand_scale=0.0")
            return False

        # Calculate delta from tracker
        delta = self._tracker.update(hand_pos, hand_scale)

        if delta is None:
            # Anchor just initialized
            return True

        # Check if movement is effectively zero
        if abs(delta.dy) < 0.0001:
            return True

        # For zoom, we only care about vertical movement
        # Positive hand_dy = hand moving down = zoom out (negative)
        # Negative hand_dy = hand moving up = zoom in (positive)
        zoom_delta = -delta.dy

        # Check if accumulated movement crosses threshold
        direction = self._tracker.accumulate(zoom_delta)

        if direction is not None:
            # Execute zoom step
            result = self.adapter.continuous_zoom(dy=direction)

            # Update tracker anchor
            self._tracker.update_anchor(hand_pos)

            log_info(f"Zoom step: direction={direction}")
            return result

        return True  # No zoom step needed yet
