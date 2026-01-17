"""
Latch control action handlers.

Handles enabling/disabling gesture control via latch state.
"""

from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.handlers.base import DiscreteActionHandler
from handsi.actions.state_machine import GestureStateMachine
from handsi.core.bus import GestureEvent, RuntimeState
from handsi.core.logging import log_debug


class EnableLatchHandler(DiscreteActionHandler):
    """
    Handler for enabling latch (turning on gesture control).
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        state_machine: GestureStateMachine
    ):
        super().__init__(adapter, runtime_state)
        self.state_machine = state_machine

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Enable latch state."""
        result = self.state_machine.enable_latch()
        if result:
            log_debug("Latch enabled")
        return result


class DisableLatchHandler(DiscreteActionHandler):
    """
    Handler for disabling latch (turning off gesture control).
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        state_machine: GestureStateMachine
    ):
        super().__init__(adapter, runtime_state)
        self.state_machine = state_machine

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Disable latch state."""
        result = self.state_machine.disable_latch()
        if result:
            log_debug("Latch disabled")
        return result
