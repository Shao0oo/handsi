"""
Click action handlers.

Handles single click, double click, and click-and-hold (drag) actions.
"""

from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.handlers.base import ActionHandler, DiscreteActionHandler
from handsi.actions.interpolation import CursorInterpolator
from handsi.core.bus import GestureEvent, RuntimeState
from handsi.core.logging import log_debug, log_error, log_info


class ClickHandler(ActionHandler):
    """
    Handler for click actions with hold/drag support.

    When gesture starts: press and hold button
    While gesture continues: allow cursor movement (drag)
    When gesture ends: release button

    This enables click-and-drag functionality.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        interpolator: CursorInterpolator,
        button: str = 'left'
    ):
        super().__init__(adapter, runtime_state)
        self.interpolator = interpolator
        self.button = button
        self._held_button: Optional[str] = None

    @property
    def is_held(self) -> bool:
        """Check if button is currently held."""
        return self._held_button is not None

    def on_gesture_start(self, event: GestureEvent) -> None:
        """Press and hold mouse button when gesture starts."""
        # Guard: prevent double-press if button already held
        if self._held_button is not None:
            log_debug(f"Ignoring duplicate gesture start, {self._held_button} already held")
            return

        # Only set state if adapter succeeds
        if self.adapter.mouse_down(self.button):
            self._held_button = self.button
            log_info(f"Pressed {self.button} button (gesture started)")
        else:
            log_error("ACT-005", f"mouse_down failed for {self.button}")
            return  # Don't enable interpolation if press failed

        # Enable interpolation for drag movement
        self.interpolator.enable()
        self.interpolator.reset_anchor()

    def on_gesture_continue(self, event: GestureEvent) -> None:
        """
        Update interpolation target for drag while button held.

        The interpolator handles smooth cursor movement during drag.
        """
        if self._held_button:
            # Update interpolation target from runtime state
            with self.runtime_state.lock:
                hand_pos = self.runtime_state.cursor_position
            self.interpolator.set_target(hand_pos)

    def on_gesture_end(self, event: GestureEvent) -> None:
        """Release mouse button when gesture ends."""
        if self._held_button:
            if self.adapter.mouse_up(self._held_button):
                log_info(f"Released {self._held_button} button (gesture ended)")
            else:
                log_error("ACT-006", f"mouse_up failed for {self._held_button}, button may be stuck")
            # Clear state regardless - user can re-trigger if needed
            self._held_button = None

        # Disable interpolation
        self.interpolator.disable()

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """
        Execute click action.

        Note: For click-and-hold behavior, the actual press/release
        is handled by on_gesture_start/end. This execute() is for
        fallback single-click behavior if needed.
        """
        return self.adapter.click(button=self.button)

    def cleanup(self) -> None:
        """Release held button on shutdown."""
        if self._held_button:
            log_info(f"Cleanup: releasing {self._held_button} button")
            self.adapter.mouse_up(self._held_button)
            self._held_button = None
        self.interpolator.disable()


class SingleClickHandler(DiscreteActionHandler):
    """
    Handler for simple single click (no hold/drag).

    Use this for actions that should just click without hold behavior.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        button: str = 'left'
    ):
        super().__init__(adapter, runtime_state)
        self.button = button

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute single click."""
        return self.adapter.click(button=self.button)


class DoubleClickHandler(DiscreteActionHandler):
    """
    Handler for double click action.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        button: str = 'left'
    ):
        super().__init__(adapter, runtime_state)
        self.button = button

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute double click."""
        return self.adapter.double_click(button=self.button)


class RightClickHandler(DiscreteActionHandler):
    """
    Handler for right click action.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState
    ):
        super().__init__(adapter, runtime_state)

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute right click."""
        return self.adapter.click(button='right')
