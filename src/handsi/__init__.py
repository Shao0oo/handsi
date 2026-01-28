"""
Handsi - Contactless Desktop Control

Phase 1: Hand tracking with adaptive FPS control.
"""

__version__ = "0.1.2"
__author__ = "Alex Shao"

# Expose main components for easier imports
from handsi.core.bus import (
    ActivityLevel,
    Frame,
    FeatureVector,
    GestureEvent,
    RuntimeState,
    create_queues,
)
from handsi.core.config import HandsiConfig, load_config
from handsi.core.logging import setup_logging

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
    "HandsiConfig",
    "load_config",
    # Logging
    "setup_logging",
]
