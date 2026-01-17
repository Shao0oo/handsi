"""
Desktop switching action handler.

Handles switching between virtual desktops/workspaces.
"""

from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.handlers.base import DiscreteActionHandler
from handsi.core.bus import GestureEvent, RuntimeState
from handsi.core.logging import log_debug, log_error


class SwitchDesktopHandler(DiscreteActionHandler):
    """
    Handler for switching virtual desktops.

    Extracts direction from gesture metadata and switches desktop.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState
    ):
        super().__init__(adapter, runtime_state)

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute desktop switch based on gesture direction."""
        if event is None:
            log_error("DSK-001", "switch_desktop requires gesture event with direction")
            return False

        # Extract direction from gesture metadata
        direction = event.metadata.get('direction')
        if not direction:
            log_error("DSK-002", "switch_desktop action missing 'direction' in metadata")
            return False

        log_debug(f"Switching desktop: direction={direction}")
        return self.adapter.switch_desktop(direction=direction)
