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
    def move_mouse_relative(self, dx: float, dy: float) -> bool:
        """
        Move mouse cursor by delta (relative movement).

        Args:
            dx: Delta X in normalized coordinates
            dy: Delta Y in normalized coordinates

        Returns:
            True if movement successful, False otherwise
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
    def mouse_down(self, button: Literal['left', 'right', 'middle'] = 'left') -> bool:
        """
        Press and hold mouse button without releasing.

        Args:
            button: Which mouse button to press

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def mouse_up(self, button: Literal['left', 'right', 'middle'] = 'left') -> bool:
        """
        Release held mouse button.

        Args:
            button: Which mouse button to release

        Returns:
            True if successful, False otherwise
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

    @abstractmethod
    def keyboard_shortcut(self, shortcut: str) -> bool:
        """
        Execute keyboard shortcut using Command key combinations.

        Args:
            shortcut: Shortcut string like 'cmd+c', 'cmd+v', 'cmd+z'

        Returns:
            True if shortcut executed successfully, False otherwise
        """
        pass

    @abstractmethod
    def reset_cursor_tracking(self) -> bool:
        """
        Reset cursor tracking to actual OS position.

        Call at gesture start to sync with actual cursor location.
        This prevents cursor teleporting after manual mouse movement.

        Returns:
            True if reset successful, False otherwise
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


def apply_smooth_dead_zone(
    dx: float,
    dy: float,
    dead_zone: float,
    curve_power: float = 2.0,
    min_damping: float = 0.1
) -> tuple[float, float]:
    """
    Apply smooth non-linear dead zone using power curve.

    Creates continuous response from heavy damping to full response:
    - Below dead_zone: Heavily damped (min_damping factor)
    - At 3x dead_zone: Full response (1.0x)
    - Smooth power curve in between

    This eliminates discontinuous jumps at the dead zone threshold,
    preventing perceivable twitches during small movements.

    Args:
        dx: Delta x movement
        dy: Delta y movement
        dead_zone: Threshold for damping region
        curve_power: Power curve exponent (1.0-3.0, higher = steeper)
        min_damping: Minimum damping factor (0.0-0.5)

    Returns:
        Smoothly damped (dx, dy) tuple
    """
    magnitude = (dx**2 + dy**2) ** 0.5

    if magnitude < 0.001:  # Avoid division by zero
        return 0.0, 0.0

    # Normalize magnitude to 0-1 range (1.0 = 3x dead_zone = full response)
    full_response_threshold = dead_zone * 3.0
    t = min(1.0, magnitude / full_response_threshold)

    # Apply power curve: t^power
    # - power=1.0: linear ramp
    # - power=2.0: quadratic (smooth, recommended)
    # - power=3.0: cubic (aggressive damping)
    damping = t ** curve_power

    # Ensure minimum damping (so small movements aren't completely killed)
    damping = max(min_damping, damping)

    # Apply damping while preserving direction
    return dx * damping, dy * damping


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
