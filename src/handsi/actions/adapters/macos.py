"""
macOS-specific action adapter using Quartz Core Graphics.

Implements ActionAdapter interface using PyObjC bindings to CGEvent APIs
for mouse/keyboard control and system-level actions.
"""

import subprocess
import time
from typing import Literal

from handsi.actions.adapters.base import ActionAdapter
from handsi.core.logging import log_debug, log_error, log_info, log_warning

try:
    from Quartz import (
        CGEventCreateMouseEvent,
        CGEventCreateScrollWheelEvent,
        CGEventPost,
        CGMainDisplayID,
        CGDisplayBounds,
        CGEventSourceCreate,
        kCGEventSourceStateHIDSystemState,
        kCGEventMouseMoved,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseUp,
        kCGEventRightMouseDown,
        kCGEventRightMouseUp,
        kCGEventOtherMouseDown,
        kCGEventOtherMouseUp,
        kCGHIDEventTap,
        kCGScrollEventUnitPixel,
    )
    from AppKit import NSEvent
    QUARTZ_AVAILABLE = True
except ImportError:
    QUARTZ_AVAILABLE = False
    log_warning("ACT-004", "PyObjC Quartz not available - macOS adapter will not function")


class MacOSAdapter(ActionAdapter):
    """
    macOS action adapter using Quartz Core Graphics.

    Requires:
    - pyobjc-framework-Quartz
    - Accessibility permissions granted in System Preferences
    """

    def __init__(self):
        self._initialized = False
        self._screen_width = 0
        self._screen_height = 0

    def initialize(self) -> bool:
        """
        Initialize macOS adapter and get screen dimensions.

        Returns:
            True if initialization successful, False otherwise
        """
        if not QUARTZ_AVAILABLE:
            log_error("ACT-004", "Quartz framework not available - install pyobjc-framework-Quartz")
            return False

        try:
            # Get screen dimensions
            main_display = CGMainDisplayID()
            bounds = CGDisplayBounds(main_display)
            self._screen_width = int(bounds.size.width)
            self._screen_height = int(bounds.size.height)

            log_info(f"macOS adapter initialized (screen: {self._screen_width}x{self._screen_height})")
            self._initialized = True
            return True

        except Exception as e:
            log_error("ACT-004", f"macOS adapter initialization failed: {e}")
            return False

    def check_permissions(self) -> bool:
        """
        Check if Accessibility permissions are granted.

        Note: There's no reliable programmatic way to check this on modern macOS.
        We'll just log a warning and let the user verify.

        Returns:
            True (always - actual permission check happens on first action)
        """
        log_info(
            "macOS Accessibility permissions required. "
            "If actions don't work, grant permissions in System Preferences > Privacy & Security > Accessibility"
        )
        return True

    def get_mouse_position_normalized(self) -> tuple[float, float]:
        """
        Get current mouse cursor position in normalized coordinates.

        Returns:
            Tuple of (x, y) where x and y are in range [0, 1] (screen percentage)
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return (0.5, 0.5)  # Fallback to center

        try:
            # Get current mouse position using NSEvent
            mouse_loc = NSEvent.mouseLocation()
            # Note: NSEvent.mouseLocation() returns Cocoa coordinates (origin at bottom-left)
            # Need to convert to Quartz coordinates (origin at top-left)
            pixel_x = mouse_loc.x
            pixel_y = self._screen_height - mouse_loc.y

            # Normalize to [0, 1] range
            normalized_x = pixel_x / self._screen_width
            normalized_y = pixel_y / self._screen_height

            # Clamp to [0, 1]
            normalized_x = max(0.0, min(1.0, normalized_x))
            normalized_y = max(0.0, min(1.0, normalized_y))

            return (normalized_x, normalized_y)

        except Exception as e:
            log_error("ACT-001", f"Get mouse position failed: {e}")
            return (0.5, 0.5)  # Fallback to center

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
            normalized: If True, x/y are in range [0, 1]
            relative: If True, move relative to current position (not supported)

        Returns:
            True if movement successful, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        try:
            # Convert normalized to screen coordinates
            if normalized:
                pixel_x = int(x * self._screen_width)
                pixel_y = int(y * self._screen_height)
            else:
                pixel_x = int(x)
                pixel_y = int(y)

            # Clamp to screen bounds
            pixel_x = max(0, min(self._screen_width - 1, pixel_x))
            pixel_y = max(0, min(self._screen_height - 1, pixel_y))

            # Create event source for proper mouse control
            source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)

            # Create and post mouse move event
            event = CGEventCreateMouseEvent(
                source,
                kCGEventMouseMoved,
                (pixel_x, pixel_y),
                0  # button number (irrelevant for move)
            )
            CGEventPost(kCGHIDEventTap, event)

            log_debug(f"Mouse moved to ({pixel_x}, {pixel_y})")
            return True

        except Exception as e:
            log_error("ACT-001", f"Mouse move failed: {e}")
            return False

    def _get_button_event_types(self, button: str) -> tuple[int, int, int]:
        """
        Get CGEvent constants for a mouse button.

        Args:
            button: 'left', 'right', or 'middle'

        Returns:
            Tuple of (down_event_type, up_event_type, button_num)

        Raises:
            ValueError: If button is invalid
        """
        if button == 'left':
            return (kCGEventLeftMouseDown, kCGEventLeftMouseUp, 0)
        elif button == 'right':
            return (kCGEventRightMouseDown, kCGEventRightMouseUp, 1)
        elif button == 'middle':
            return (kCGEventOtherMouseDown, kCGEventOtherMouseUp, 2)
        else:
            raise ValueError(f"Invalid mouse button: {button}")

    def mouse_down(self, button: Literal['left', 'right', 'middle'] = 'left') -> bool:
        """
        Press and hold mouse button without releasing.

        Args:
            button: Which mouse button to press

        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        try:
            down_event_type, _, button_num = self._get_button_event_types(button)

            # Query current mouse position
            mouse_loc = NSEvent.mouseLocation()
            pos = (int(mouse_loc.x), int(self._screen_height - mouse_loc.y))

            # Create and post mouse down event (hold button)
            down_event = CGEventCreateMouseEvent(
                None,
                down_event_type,
                pos,
                button_num
            )
            CGEventPost(kCGHIDEventTap, down_event)

            log_debug(f"Mouse {button} button pressed (held)")
            return True

        except Exception as e:
            log_error("ACT-001", f"Mouse down failed: {e}")
            return False

    def mouse_up(self, button: Literal['left', 'right', 'middle'] = 'left') -> bool:
        """
        Release held mouse button.

        Args:
            button: Which mouse button to release

        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        try:
            _, up_event_type, button_num = self._get_button_event_types(button)

            # Query current mouse position
            mouse_loc = NSEvent.mouseLocation()
            pos = (int(mouse_loc.x), int(self._screen_height - mouse_loc.y))

            # Create and post mouse up event (release button)
            up_event = CGEventCreateMouseEvent(
                None,
                up_event_type,
                pos,
                button_num
            )
            CGEventPost(kCGHIDEventTap, up_event)

            log_debug(f"Mouse {button} button released")
            return True

        except Exception as e:
            log_error("ACT-001", f"Mouse up failed: {e}")
            return False

    def click(self, button: Literal['left', 'right', 'middle'] = 'left') -> bool:
        """
        Perform a mouse click (press and release).

        Args:
            button: Which mouse button to click

        Returns:
            True if click successful, False otherwise
        """
        # Refactored to use mouse_down() and mouse_up()
        if not self.mouse_down(button):
            return False
        return self.mouse_up(button)
    
    def double_click(self, button: Literal['left', 'right', 'middle'] = 'left') -> bool:
        """
        Perform a double mouse click.

        Args:
            button: Which mouse button to click

        Returns:
            True if click successful, False otherwise
        """
        
        if not self.mouse_down(button):
            print("Failed on: mouse down first click")
            return False
        if not self.mouse_up(button):
            print("Failed on: mouse up first click")
            return False
        time.sleep(0.1)
        if not self.mouse_down(button):
            print("Failed on: mouse down second click")
            return False
        return self.mouse_up(button)
    

    def scroll(self, dx: int = 0, dy: int = 0) -> bool:
        """
        Scroll the mouse wheel.

        Args:
            dx: Horizontal scroll amount (pixels)
            dy: Vertical scroll amount (pixels, positive = down)

        Returns:
            True if scroll successful, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        try:
            # CGEventCreateScrollWheelEvent uses scroll lines, not pixels
            # We'll convert pixels to lines (rough approximation)
            scroll_lines = dy // 10  # Approximate: 10 pixels = 1 line

            if scroll_lines == 0 and dy != 0:
                scroll_lines = 1 if dy > 0 else -1

            # Create and post scroll event
            # Note: macOS scroll is inverted (negative = down)
            event = CGEventCreateScrollWheelEvent(
                None,
                kCGScrollEventUnitPixel,
                1,  # Number of wheels (1 for vertical)
                -scroll_lines  # Invert for natural scrolling
            )
            CGEventPost(kCGHIDEventTap, event)

            log_debug(f"Scroll executed: dy={dy} (lines={scroll_lines})")
            return True

        except Exception as e:
            log_error("ACT-001", f"Scroll failed: {e}")
            return False

    def zoom(self, direction: Literal['in', 'out'], step: float = 0.1) -> bool:
        """
        Zoom in or out using system-wide zoom (Accessibility zoom).

        Args:
            direction: 'in' to zoom in, 'out' to zoom out
            step: Zoom increment (ignored - macOS zoom is toggle-based)

        Returns:
            True if zoom successful, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        try:
            # Use AppleScript to trigger macOS accessibility zoom
            # This requires "Use scroll gesture with modifier keys to zoom" enabled
            # Alternative: Use Cmd+Plus/Minus for browser zoom

            # For now, we'll simulate browser zoom using keyboard shortcut
            # This requires implementing keyboard event posting

            log_warning("ACT-001", "Zoom action not yet fully implemented")
            return False

        except Exception as e:
            log_error("ACT-001", f"Zoom failed: {e}")
            return False

    def switch_desktop(self, direction: Literal['left', 'right', 'next', 'prev']) -> bool:
        """
        Switch to adjacent virtual desktop using Mission Control.

        Args:
            direction: Direction to switch ('left'/'prev' or 'right'/'next')

        Returns:
            True if switch successful, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        try:
            # Map direction
            if direction in ('left', 'prev'):
                # Ctrl+Left Arrow
                key_code = 123  # Left arrow
            elif direction in ('right', 'next'):
                # Ctrl+Right Arrow
                key_code = 124  # Right arrow
            else:
                log_error("ACT-003", f"Invalid desktop switch direction: {direction}")
                return False

            # Use AppleScript to simulate keyboard shortcut
            # This is more reliable than CGEventCreateKeyboardEvent
            script = f'''
            tell application "System Events"
                key code {key_code} using control down
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=2.0
            )

            if result.returncode == 0:
                log_debug(f"Desktop switched: {direction}")
                return True
            else:
                log_warning("ACT-001", f"Desktop switch failed: {result.stderr}")
                return False

        except Exception as e:
            log_error("ACT-001", f"Desktop switch failed: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up macOS adapter resources."""
        log_info("macOS adapter cleaned up")
        self._initialized = False
