"""
OS-specific action adapters.

Provides platform-specific implementations for mouse, keyboard,
and system actions.
"""

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.adapters.ipc import IPCAdapter

__all__ = ["ActionAdapter", "IPCAdapter"]
