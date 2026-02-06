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
    Handler for copy action.

    Executes copy using platform-specific shortcut (Cmd+C on macOS, Ctrl+C on Linux).
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState
    ):
        super().__init__(adapter, runtime_state)

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute copy action."""
        log_debug("Executing copy action")
        return self.adapter.semantic_action("copy")


class PasteHandler(DiscreteActionHandler):
    """
    Handler for paste action.

    Executes paste using platform-specific shortcut (Cmd+V on macOS, Ctrl+V on Linux).
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState
    ):
        super().__init__(adapter, runtime_state)

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute paste action."""
        log_debug("Executing paste action")
        return self.adapter.semantic_action("paste")


class UndoHandler(DiscreteActionHandler):
    """
    Handler for undo action.

    Executes undo using platform-specific shortcut (Cmd+Z on macOS, Ctrl+Z on Linux).
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState
    ):
        super().__init__(adapter, runtime_state)

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute undo action."""
        log_debug("Executing undo action")
        return self.adapter.semantic_action("undo")
