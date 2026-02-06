"""
Action handlers for gesture-triggered actions.

Each handler implements a specific action type (click, scroll, zoom, etc.)
following the ActionHandler interface.
"""

from handsi.actions.handlers.alert import (
    AudioAlertHandler,
    CompositeAlertHandler,
    VisualAlertHandler,
)
from handsi.actions.handlers.base import (
    ActionHandler,
    ContinuousActionHandler,
    DiscreteActionHandler,
)
from handsi.actions.handlers.click import (
    ClickHandler,
    DoubleClickHandler,
    RightClickHandler,
    SingleClickHandler,
)
from handsi.actions.handlers.desktop import SwitchDesktopHandler
from handsi.actions.handlers.keyboard import CopyHandler, PasteHandler, UndoHandler
from handsi.actions.handlers.latch import DisableLatchHandler, EnableLatchHandler
from handsi.actions.handlers.mouse import MouseMoveHandler
from handsi.actions.handlers.scroll import ContinuousScrollHandler, ScrollStepHandler
from handsi.actions.handlers.tab import ContinuousTabHandler
from handsi.actions.handlers.volume import ContinuousVolumeHandler
from handsi.actions.handlers.zoom import ContinuousZoomHandler, ZoomStepHandler

__all__ = [
    # Base classes
    "ActionHandler",
    "ContinuousActionHandler",
    "DiscreteActionHandler",
    # Click handlers
    "ClickHandler",
    "SingleClickHandler",
    "DoubleClickHandler",
    "RightClickHandler",
    # Movement handlers
    "MouseMoveHandler",
    # Scroll handlers
    "ScrollStepHandler",
    "ContinuousScrollHandler",
    # Zoom handlers
    "ZoomStepHandler",
    "ContinuousZoomHandler",
    # Volume handler
    "ContinuousVolumeHandler",
    # Tab handler
    "ContinuousTabHandler",
    # Desktop handler
    "SwitchDesktopHandler",
    # Keyboard handlers
    "CopyHandler",
    "PasteHandler",
    "UndoHandler",
    # Latch handlers
    "EnableLatchHandler",
    "DisableLatchHandler",
    # Alert handlers
    "CompositeAlertHandler",
    "VisualAlertHandler",
    "AudioAlertHandler",
]
