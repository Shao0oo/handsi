"""
OS-specific action adapters.

Provides platform-specific implementations for mouse, keyboard,
and system actions.
"""

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.adapters.factory import AdapterFactory

__all__ = ["ActionAdapter", "AdapterFactory"]
