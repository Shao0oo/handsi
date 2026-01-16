"""
Adapter factory for platform-specific action adapters.

Uses a registry pattern to allow adapters to self-register,
enabling the Open/Closed Principle - new platforms can be
added without modifying the factory.
"""

import platform
from typing import Dict, Optional, Type

from handsi.actions.adapters.base import ActionAdapter
from handsi.core.logging import log_error, log_info


class AdapterFactory:
    """
    Factory for creating platform-specific action adapters.

    Uses a registry pattern where adapters register themselves,
    allowing new platforms to be added without modifying this class.

    Usage:
        # Get adapter for current platform
        adapter = AdapterFactory.create()

        # Or specify platform explicitly
        adapter = AdapterFactory.create("Darwin")

    Adding new platforms:
        1. Create adapter class implementing ActionAdapter
        2. Call AdapterFactory.register("PlatformName", AdapterClass)
        3. (Optional) Auto-register in adapter module __init__.py
    """

    _registry: Dict[str, Type[ActionAdapter]] = {}

    @classmethod
    def register(cls, platform_name: str, adapter_class: Type[ActionAdapter]) -> None:
        """
        Register an adapter class for a platform.

        Args:
            platform_name: Platform identifier (e.g., "Darwin", "Linux", "Windows")
            adapter_class: ActionAdapter subclass for this platform
        """
        cls._registry[platform_name] = adapter_class
        log_info(f"Registered adapter for platform: {platform_name}")

    @classmethod
    def create(cls, platform_name: Optional[str] = None) -> Optional[ActionAdapter]:
        """
        Create an adapter for the specified or current platform.

        Args:
            platform_name: Platform to create adapter for.
                          If None, uses current platform.

        Returns:
            ActionAdapter instance, or None if platform not supported
        """
        if platform_name is None:
            platform_name = platform.system()

        if platform_name not in cls._registry:
            log_error("ADP-001", f"No adapter registered for platform: {platform_name}")
            log_info(f"Registered platforms: {list(cls._registry.keys())}")
            return None

        adapter_class = cls._registry[platform_name]
        log_info(f"Creating adapter for platform: {platform_name}")
        return adapter_class()

    @classmethod
    def is_supported(cls, platform_name: Optional[str] = None) -> bool:
        """
        Check if a platform is supported.

        Args:
            platform_name: Platform to check. If None, uses current platform.

        Returns:
            True if platform has a registered adapter
        """
        if platform_name is None:
            platform_name = platform.system()
        return platform_name in cls._registry

    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """
        Get list of supported platform names.

        Returns:
            List of platform names with registered adapters
        """
        return list(cls._registry.keys())

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered adapters.

        Primarily for testing purposes.
        """
        cls._registry.clear()


# Auto-register adapters based on platform availability
def _auto_register_adapters() -> None:
    """
    Automatically register available platform adapters.

    This attempts to import each platform's adapter and register it.
    Import failures are silently ignored (platform deps not available).
    """
    # macOS adapter
    try:
        from handsi.actions.adapters.macos import MacOSAdapter
        AdapterFactory.register("Darwin", MacOSAdapter)
    except ImportError:
        pass  # macOS dependencies not available

    # Linux adapter (when implemented)
    try:
        from handsi.actions.adapters.linux import LinuxAdapter
        AdapterFactory.register("Linux", LinuxAdapter)
    except ImportError:
        pass  # Linux dependencies not available

    # Windows adapter (when implemented)
    try:
        from handsi.actions.adapters.windows import WindowsAdapter
        AdapterFactory.register("Windows", WindowsAdapter)
    except ImportError:
        pass  # Windows dependencies not available


# Auto-register on module import
_auto_register_adapters()
