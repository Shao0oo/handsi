"""
Keyboard shortcut action handlers.

Handles copy, paste, and undo keyboard shortcuts.
"""

from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.handlers.base import DiscreteActionHandler
from handsi.core.bus import GestureEvent, RuntimeState
from handsi.core.logging import log_debug


class CopyHandler(DiscreteActionHandler):
    """
    Handler for copy action (Cmd+C).

    Executes copy keyboard shortcut when triggered.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState
    ):
        super().__init__(adapter, runtime_state)

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute copy keyboard shortcut."""
        log_debug("Executing copy action")
        return self.adapter.keyboard_shortcut('cmd+c')


class PasteHandler(DiscreteActionHandler):
    """
    Handler for paste action (Cmd+V).

    Executes paste keyboard shortcut when triggered.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState
    ):
        super().__init__(adapter, runtime_state)

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute paste keyboard shortcut."""
        log_debug("Executing paste action")
        return self.adapter.keyboard_shortcut('cmd+v')


class UndoHandler(DiscreteActionHandler):
    """
    Handler for undo action (Cmd+Z).

    Executes undo keyboard shortcut when triggered.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState
    ):
        super().__init__(adapter, runtime_state)

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute undo keyboard shortcut."""
        log_debug("Executing undo action")
        return self.adapter.keyboard_shortcut('cmd+z')
