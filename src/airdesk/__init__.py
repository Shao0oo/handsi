"""
AirDesk - Contactless Desktop Control

Phase 1: Hand tracking with adaptive FPS control.
"""

__version__ = "0.1.0"
__author__ = "Alex Shao"

# Expose main components for easier imports
from airdesk.core.bus import (
    ActivityLevel,
    Frame,
    FeatureVector,
    GestureEvent,
    RuntimeState,
    create_queues,
)
from airdesk.core.config import AirDeskConfig, load_config
from airdesk.core.logging import setup_logging

__all__ = [
    # Version
    "__version__",
    "__author__",
    # Core types
    "ActivityLevel",
    "Frame",
    "FeatureVector",
    "GestureEvent",
    "RuntimeState",
    "create_queues",
    # Config
    "AirDeskConfig",
    "load_config",
    # Logging
    "setup_logging",
]
