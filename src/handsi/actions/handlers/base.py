"""
Base class for action handlers.

Defines the interface that all action handlers must implement,
providing lifecycle hooks for gesture start, continue, and end.
"""

from abc import ABC, abstractmethod
from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.core.bus import GestureEvent, RuntimeState


class ActionHandler(ABC):
    """
    Base class for action handlers.

    Each action handler is responsible for executing a specific type of action
    (click, scroll, zoom, etc.) in response to gestures. Handlers receive
    lifecycle callbacks for gesture start, continue, and end events.

    Subclasses must implement execute() and may override lifecycle methods
    for stateful actions (like continuous scroll or click-and-drag).
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState
    ):
        """
        Initialize the handler.

        Args:
            adapter: OS-specific adapter for action execution
            runtime_state: Shared runtime state
        """
        self.adapter = adapter
        self.runtime_state = runtime_state

    @abstractmethod
    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """
        Execute the action.

        This is the main action execution method, called when the action
        should be performed (either from queue processing or continuous
        gesture handling).

        Args:
            event: Optional gesture event that triggered this action

        Returns:
            True if action executed successfully, False otherwise
        """
        pass

    def on_gesture_start(self, event: GestureEvent) -> None:
        """
        Called when a gesture mapped to this action starts.

        Override this method for actions that need initialization when
        the gesture begins (e.g., setting anchor positions, enabling
        interpolation, pressing mouse buttons).

        Args:
            event: The gesture event that started
        """
        pass

    def on_gesture_continue(self, event: GestureEvent) -> None:
        """
        Called while a gesture mapped to this action continues.

        Override this method for continuous actions that need per-frame
        updates (e.g., scroll tracking, zoom accumulation).

        The default implementation calls execute().

        Args:
            event: The continuing gesture event
        """
        self.execute(event)

    def on_gesture_end(self, event: GestureEvent) -> None:
        """
        Called when a gesture mapped to this action ends.

        Override this method for actions that need cleanup when the
        gesture stops (e.g., releasing mouse buttons, triggering
        momentum, resetting state).

        Args:
            event: The gesture event that ended
        """
        pass

    def cleanup(self) -> None:
        """
        Clean up handler resources.

        Called during shutdown. Override if cleanup is needed.
        """
        pass


class DiscreteActionHandler(ActionHandler):
    """
    Base class for discrete (one-shot) action handlers.

    Discrete actions are executed once per trigger (e.g., single click,
    scroll step). They don't maintain state between calls.
    """

    def on_gesture_continue(self, event: GestureEvent) -> None:
        """
        Discrete actions don't execute on continue - only on start/trigger.

        Override this if the discrete action should repeat while held.
        """
        pass


class ContinuousActionHandler(ActionHandler):
    """
    Base class for continuous action handlers.

    Continuous actions track state over time (e.g., continuous scroll,
    continuous zoom, mouse movement). They typically use anchor positions
    and delta calculations.
    """

    def reset_tracking(self) -> None:
        """
        Reset tracking state.

        Override to reset anchor positions, accumulators, etc.
        Called on gesture start and cleanup.
        """
        pass

    def on_gesture_start(self, event: GestureEvent) -> None:
        """Reset tracking when gesture starts."""
        self.reset_tracking()

    def on_gesture_end(self, event: GestureEvent) -> None:
        """Reset tracking when gesture ends."""
        self.reset_tracking()
