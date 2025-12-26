"""
Abstract base class for OS-specific action adapters.

Defines the interface for executing system actions (mouse, keyboard, zoom, etc.)
across different operating systems.
"""

from abc import ABC, abstractmethod
from typing import Literal, Optional


class ActionAdapter(ABC):
    """
    Abstract base class for OS-specific action execution.

    Each OS adapter (macOS, Linux, Windows) must implement these methods
    to execute system-level actions like mouse movement, clicks, scrolling, etc.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the adapter and verify system permissions.

        Returns:
            True if initialization successful and permissions granted, False otherwise
        """
        pass

    @abstractmethod
    def check_permissions(self) -> bool:
        """
        Check if necessary OS permissions are granted.

        Returns:
            True if all required permissions are granted, False otherwise
        """
        pass

    @abstractmethod
    def move_mouse(
        self,
        x: float,
        y: float,
        normalized: bool = True,
        relative: bool = False
    ) -> bool:
        """
        Move mouse cursor to specified position.

        Args:
            x: X coordinate (0-1 if normalized, pixels if not)
            y: Y coordinate (0-1 if normalized, pixels if not)
            normalized: If True, x/y are in range [0, 1] (screen percentage)
            relative: If True, move relative to current position (delta)

        Returns:
            True if movement successful, False otherwise
        """
        pass

    @abstractmethod
    def click(self, button: Literal['left', 'right', 'middle'] = 'left') -> bool:
        """
        Perform a mouse click.

        Args:
            button: Which mouse button to click

        Returns:
            True if click successful, False otherwise
        """
        pass

    @abstractmethod
    def scroll(self, dx: int = 0, dy: int = 0) -> bool:
        """
        Scroll the mouse wheel.

        Args:
            dx: Horizontal scroll amount (pixels)
            dy: Vertical scroll amount (pixels, positive = down)

        Returns:
            True if scroll successful, False otherwise
        """
        pass

    @abstractmethod
    def zoom(self, direction: Literal['in', 'out'], step: float = 0.1) -> bool:
        """
        Zoom in or out (system-wide zoom or browser zoom).

        Args:
            direction: 'in' to zoom in, 'out' to zoom out
            step: Zoom increment (e.g., 0.1 = 10%)

        Returns:
            True if zoom successful, False otherwise
        """
        pass

    @abstractmethod
    def switch_desktop(self, direction: Literal['left', 'right', 'next', 'prev']) -> bool:
        """
        Switch to adjacent virtual desktop/workspace.

        Args:
            direction: Direction to switch ('left'/'prev' or 'right'/'next')

        Returns:
            True if switch successful, False otherwise
        """
        pass

    def cleanup(self) -> None:
        """
        Clean up adapter resources.

        Called during shutdown. Override if cleanup needed.
        """
        pass


def normalize_position(
    x: float,
    y: float,
    screen_width: int,
    screen_height: int,
    hand_scale: float,
    sensitivity: float = 1.0
) -> tuple[int, int]:
    """
    Convert normalized hand position to screen coordinates.

    Args:
        x: Normalized x position (0-1)
        y: Normalized y position (0-1)
        screen_width: Screen width in pixels
        screen_height: Screen height in pixels
        hand_scale: Current hand size (for scale-invariant movement)
        sensitivity: Movement sensitivity multiplier

    Returns:
        Tuple of (pixel_x, pixel_y) screen coordinates
    """
    # Apply sensitivity
    x_adj = x * sensitivity
    y_adj = y * sensitivity

    # Clamp to [0, 1]
    x_adj = max(0.0, min(1.0, x_adj))
    y_adj = max(0.0, min(1.0, y_adj))

    # Convert to screen pixels
    pixel_x = int(x_adj * screen_width)
    pixel_y = int(y_adj * screen_height)

    return pixel_x, pixel_y


def apply_dead_zone(
    dx: float,
    dy: float,
    dead_zone: float
) -> tuple[float, float]:
    """
    Apply dead zone to movement delta (ignore small jitters).

    Args:
        dx: Delta x movement
        dy: Delta y movement
        dead_zone: Minimum movement threshold

    Returns:
        Tuple of (adjusted_dx, adjusted_dy), zeroed if within dead zone
    """
    magnitude = (dx**2 + dy**2) ** 0.5

    if magnitude < dead_zone:
        return 0.0, 0.0

    return dx, dy


def smooth_position(
    current: tuple[float, float],
    target: tuple[float, float],
    smoothing_factor: float
) -> tuple[float, float]:
    """
    Apply exponential moving average (EMA) smoothing to position.

    Args:
        current: Current position (x, y)
        target: Target position (x, y)
        smoothing_factor: Smoothing factor (0=no smoothing, 1=max smoothing)

    Returns:
        Smoothed position (x, y)
    """
    alpha = 1.0 - smoothing_factor

    smoothed_x = alpha * target[0] + smoothing_factor * current[0]
    smoothed_y = alpha * target[1] + smoothing_factor * current[1]

    return smoothed_x, smoothed_y
