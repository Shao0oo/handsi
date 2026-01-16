"""
Mouse movement action handler.

Handles cursor movement using interpolation for smooth tracking.
"""

from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.handlers.base import ContinuousActionHandler
from handsi.actions.interpolation import CursorInterpolator
from handsi.core.bus import GestureEvent, RuntimeState
from handsi.core.logging import log_debug


class MouseMoveHandler(ContinuousActionHandler):
    """
    Handler for mouse movement.

    Delegates actual movement to CursorInterpolator for smooth,
    high-frequency cursor updates (60Hz vs 10Hz gesture detection).
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        interpolator: CursorInterpolator
    ):
        super().__init__(adapter, runtime_state)
        self.interpolator = interpolator

    def reset_tracking(self) -> None:
        """Reset mouse movement tracking."""
        self.interpolator.reset_anchor()

    def on_gesture_start(self, event: GestureEvent) -> None:
        """Handle mouse_move gesture start."""
        self.reset_tracking()
        self.interpolator.enable()
        log_debug("Interpolation enabled (mouse_move started)")

    def on_gesture_continue(self, event: GestureEvent) -> None:
        """Update interpolation target while gesture active."""
        self.execute(event)

    def on_gesture_end(self, event: GestureEvent) -> None:
        """Handle mouse_move gesture end."""
        self.interpolator.disable()
        log_debug("Interpolation disabled (gesture ended)")

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """
        Update interpolation target for smooth cursor movement.

        The actual cursor movement is handled by the interpolation
        thread at 60Hz for smooth tracking.
        """
        with self.runtime_state.lock:
            hand_pos = self.runtime_state.cursor_position
            hand_scale = self.runtime_state.hand_scale

        if hand_scale == 0.0:
            # No valid hand detected
            return False

        # Update interpolation target
        self.interpolator.set_target(hand_pos)
        return True
