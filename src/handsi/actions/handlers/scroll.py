"""
Scroll action handlers.

Handles both discrete scroll steps and continuous scroll tracking
with momentum support.
"""

from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.continuous_tracker import ContinuousActionTracker, ContinuousTrackerConfig
from handsi.actions.handlers.base import ContinuousActionHandler, DiscreteActionHandler
from handsi.actions.momentum import ScrollMomentum
from handsi.core.bus import GestureEvent, RuntimeState
from handsi.core.config import ScrollConfig
from handsi.core.logging import log_debug


class ScrollStepHandler(DiscreteActionHandler):
    """
    Handler for discrete scroll steps (scroll_up, scroll_down).

    Executes a single scroll step in the specified direction.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        scroll_config: ScrollConfig,
        direction: str  # 'up' or 'down'
    ):
        super().__init__(adapter, runtime_state)
        self.scroll_config = scroll_config
        self.direction = direction

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute a single scroll step."""
        scroll_speed = self.scroll_config.scroll_speed

        if self.direction == 'down':
            dy = scroll_speed
        elif self.direction == 'up':
            dy = -scroll_speed
        else:
            log_debug(f"Invalid scroll direction: {self.direction}")
            return False

        return self.adapter.scroll(dx=0, dy=dy)


class ContinuousScrollHandler(ContinuousActionHandler):
    """
    Handler for continuous scroll tracking.

    Tracks hand vertical movement and converts to scroll events.
    Supports momentum (kinetic scrolling) after gesture ends.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        scroll_config: ScrollConfig,
        momentum: ScrollMomentum
    ):
        super().__init__(adapter, runtime_state)
        self.scroll_config = scroll_config
        self.momentum = momentum

        # Create tracker with scroll config
        tracker_config = ContinuousTrackerConfig(
            dead_zone=scroll_config.dead_zone,
            dead_zone_curve=scroll_config.dead_zone_curve,
            dead_zone_min_damping=scroll_config.dead_zone_min_damping,
            sensitivity=scroll_config.sensitivity
        )
        self._tracker = ContinuousActionTracker(tracker_config)

    def reset_tracking(self) -> None:
        """Reset scroll tracking state."""
        self._tracker.reset()

    def on_gesture_start(self, event: GestureEvent) -> None:
        """Handle scroll gesture start."""
        # Cancel any active momentum (user taking control)
        self.momentum.cancel()
        self.reset_tracking()
        log_debug("Scroll tracking started")

    def on_gesture_continue(self, event: GestureEvent) -> None:
        """Handle continuous scroll while gesture active."""
        self.execute(event)

    def on_gesture_end(self, event: GestureEvent) -> None:
        """Handle scroll gesture end - trigger momentum."""
        self.momentum.trigger()
        self.reset_tracking()
        log_debug("Scroll tracking stopped")

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute continuous scroll based on hand movement."""
        # Get hand position and scale
        with self.runtime_state.lock:
            hand_pos = self.runtime_state.cursor_position
            hand_scale = self.runtime_state.hand_scale

        if hand_scale == 0.0:
            log_debug("Scroll skipped: hand_scale=0.0")
            return False

        # Calculate delta from tracker
        delta = self._tracker.update(hand_pos, hand_scale)

        if delta is None:
            # Anchor just initialized
            return True

        # Check if movement is effectively zero
        if abs(delta.dx) < 0.0001 and abs(delta.dy) < 0.0001:
            return True

        # Determine dominant scroll direction
        abs_dx = abs(delta.dx)
        abs_dy = abs(delta.dy)

        if abs_dy > abs_dx:
            # Vertical scrolling dominant
            scroll_amount_x = 0.0
            scroll_amount_y = delta.dy * self.scroll_config.sensitivity * 1000
        else:
            # Horizontal scrolling dominant
            scroll_amount_x = delta.dx * self.scroll_config.sensitivity * 1000
            scroll_amount_y = 0.0

        # Record velocity for momentum (before inversion)
        self.momentum.record_velocity(scroll_amount_x, scroll_amount_y)

        # Apply invert if enabled (natural scrolling)
        if self.scroll_config.invert:
            scroll_amount_y = -scroll_amount_y

        # Clamp to max scroll per frame
        max_scroll = self.scroll_config.max_scroll_per_frame
        scroll_amount_x = max(-max_scroll, min(max_scroll, scroll_amount_x))
        scroll_amount_y = max(-max_scroll, min(max_scroll, scroll_amount_y))

        log_debug(f"Scroll: dx={scroll_amount_x:.1f}px, dy={scroll_amount_y:.1f}px")

        # Execute scroll
        result = self.adapter.scroll(dx=int(scroll_amount_x), dy=int(scroll_amount_y))

        # Update tracker anchor
        self._tracker.update_anchor(hand_pos)

        return result
