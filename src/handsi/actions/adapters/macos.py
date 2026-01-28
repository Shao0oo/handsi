"""
macOS-specific action adapter using Quartz Core Graphics.

Implements ActionAdapter interface using PyObjC bindings to CGEvent APIs
for mouse/keyboard control and system-level actions.
"""

import subprocess
import time
from typing import Literal

from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.core.logging import log_debug, log_error, log_info, log_warning

try:
    from Quartz import (
        CGEventCreateMouseEvent,
        CGEventCreateScrollWheelEvent,
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGMainDisplayID,
        CGDisplayBounds,
        CGGetActiveDisplayList,
        CGEventSourceCreate,
        CGEventSetIntegerValueField,
        CGEventSetFlags,
        kCGEventSourceStateHIDSystemState,
        kCGEventMouseMoved,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseUp,
        kCGEventLeftMouseDragged,
        kCGEventRightMouseDown,
        kCGEventRightMouseUp,
        kCGEventRightMouseDragged,
        kCGEventOtherMouseDown,
        kCGEventOtherMouseUp,
        kCGMouseEventClickState,
        kCGHIDEventTap,
        kCGScrollEventUnitPixel,
        kCGScrollEventUnitLine,
        kCGEventFlagMaskCommand,
        kCGEventFlagMaskControl,
        kCGEventFlagMaskShift,
        kCGEventKeyDown,
        kCGEventKeyUp,
    )
    from AppKit import NSEvent
    from Foundation import NSAppleScript
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
        self._screen_x_offset = 0  # X offset of the combined display bounds (Quartz coords)
        self._screen_y_offset = 0  # Y offset of the combined display bounds (Quartz coords)
        self._main_display_height = 0  # Height of main display (for Cocoa coordinate conversion)
        self._double_click_threshold = 0.5  # Default 500ms, will be queried from system
        self._held_button: Optional[str] = None  # Track which button is currently held for drag events

    def initialize(self) -> bool:
        """
        Initialize macOS adapter and get screen dimensions.

        For multi-monitor setups, this calculates the combined bounding box
        that encompasses all active displays.

        Returns:
            True if initialization successful, False otherwise
        """
        if not QUARTZ_AVAILABLE:
            log_error("ACT-004", "Quartz framework not available - install pyobjc-framework-Quartz")
            return False

        try:
            # Get main display ID for Cocoa coordinate reference
            main_display_id = CGMainDisplayID()
            main_display_bounds = CGDisplayBounds(main_display_id)
            self._main_display_height = int(main_display_bounds.size.height)

            # Get all active displays for multi-monitor support
            max_displays = 16  # Reasonable upper limit for display count
            (err, active_displays, display_count) = CGGetActiveDisplayList(max_displays, None, None)

            if err != 0 or display_count == 0:
                log_error("ACT-004", f"Failed to get active display list (error: {err})")
                return False

            # Calculate combined bounding box across all displays
            min_x = float('inf')
            min_y = float('inf')
            max_x = float('-inf')
            max_y = float('-inf')

            for display_id in active_displays[:display_count]:
                bounds = CGDisplayBounds(display_id)
                display_min_x = bounds.origin.x
                display_min_y = bounds.origin.y
                display_max_x = display_min_x + bounds.size.width
                display_max_y = display_min_y + bounds.size.height

                min_x = min(min_x, display_min_x)
                min_y = min(min_y, display_min_y)
                max_x = max(max_x, display_max_x)
                max_y = max(max_y, display_max_y)

                is_main = " (main)" if display_id == main_display_id else ""
                log_debug(f"Display {display_id}{is_main}: origin=({display_min_x}, {display_min_y}), size=({bounds.size.width}, {bounds.size.height})")

            # Store combined screen dimensions and offset
            self._screen_x_offset = int(min_x)
            self._screen_y_offset = int(min_y)
            self._screen_width = int(max_x - min_x)
            self._screen_height = int(max_y - min_y)

            # Query macOS double-click threshold
            try:
                result = subprocess.run(
                    ['defaults', 'read', '-g', 'com.apple.mouse.doubleClickThreshold'],
                    capture_output=True,
                    text=True,
                    timeout=1.0
                )
                if result.returncode == 0:
                    self._double_click_threshold = float(result.stdout.strip())
                    log_info(f"macOS double-click threshold: {self._double_click_threshold}s")
                else:
                    log_warning("ACT-004", f"Failed to read double-click threshold, using default: {self._double_click_threshold}s")
            except Exception as e:
                log_warning("ACT-004", f"Error querying double-click threshold: {e}, using default")

            # # Check zoom scroll gesture settings
            # self.check_zoom_settings()

            log_info(
                f"macOS adapter initialized (combined screen: {self._screen_width}x{self._screen_height}, "
                f"offset: ({self._screen_x_offset}, {self._screen_y_offset}), "
                f"displays: {display_count})"
            )
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

    def check_zoom_settings(self) -> bool:
        """
        Check if macOS zoom scroll gesture is enabled.

        Checks system settings for:
        - closeViewScrollWheelToggle (whether zoom scroll is enabled)
        - closeViewScrollWheelModifiersInt (which modifier key: 2 = Control)

        Logs a warning if settings are not properly configured for continuous_zoom action.

        Returns:
            True if zoom settings are properly configured, False otherwise
        """
        try:
            # Check if scroll wheel zoom is enabled
            result_toggle = subprocess.run(
                ['defaults', 'read', 'com.apple.universalaccess', 'closeViewScrollWheelToggle'],
                capture_output=True,
                text=True,
                timeout=1.0
            )

            # Check which modifier key is set
            result_modifier = subprocess.run(
                ['defaults', 'read', 'com.apple.universalaccess', 'closeViewScrollWheelModifiersInt'],
                capture_output=True,
                text=True,
                timeout=1.0
            )

            zoom_enabled = False
            control_modifier = False

            # Parse toggle (should be 1 for enabled)
            if result_toggle.returncode == 0:
                try:
                    toggle_value = int(result_toggle.stdout.strip())
                    zoom_enabled = (toggle_value == 1)
                except ValueError:
                    pass

            # Parse modifier (should be 2 for Control key)
            if result_modifier.returncode == 0:
                try:
                    modifier_value = int(result_modifier.stdout.strip())
                    control_modifier = (modifier_value == 2)
                except ValueError:
                    pass

            # Warn user if not properly configured
            if not zoom_enabled or not control_modifier:
                log_warning(
                    "ACT-004",
                    "Zoom scroll gesture not enabled or using wrong modifier. "
                    "To use continuous_zoom action, enable in: "
                    "System Settings > Accessibility > Zoom > 'Use scroll gesture with modifier keys to zoom' "
                    "(ensure Control key is selected as modifier)"
                )
                return False
            else:
                log_info("macOS zoom scroll gesture properly configured (Control + scroll)")
                return True

        except Exception as e:
            log_warning("ACT-004", f"Could not check zoom settings: {e}")
            return False

    def get_mouse_position_normalized(self) -> tuple[float, float]:
        """
        Get current mouse cursor position in normalized coordinates.

        For multi-monitor setups, coordinates are normalized relative to the
        combined bounding box of all displays.

        Returns:
            Tuple of (x, y) where x and y are in range [0, 1] (screen percentage)
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return (0.5, 0.5)  # Fallback to center

        try:
            # Get current mouse position using NSEvent (Cocoa coordinates)
            # Cocoa: origin at bottom-left of main display, Y increases upward
            mouse_loc = NSEvent.mouseLocation()
            cocoa_x = mouse_loc.x
            cocoa_y = mouse_loc.y

            # Convert from Cocoa to Quartz coordinates
            # Quartz: origin at top-left of virtual desktop, Y increases downward
            # Formula: quartz_y = main_display_height - cocoa_y
            quartz_x = cocoa_x
            quartz_y = self._main_display_height - cocoa_y

            # Normalize to [0, 1] range relative to combined display bounds
            normalized_x = (quartz_x - self._screen_x_offset) / self._screen_width
            normalized_y = (quartz_y - self._screen_y_offset) / self._screen_height

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

        Automatically uses drag events when a button is held down.
        For multi-monitor setups, coordinates span the combined display area.

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
            # Convert normalized to screen coordinates (relative to combined display bounds)
            if normalized:
                pixel_x = int(x * self._screen_width) + self._screen_x_offset
                pixel_y = int(y * self._screen_height) + self._screen_y_offset
            else:
                pixel_x = int(x)
                pixel_y = int(y)

            # Clamp to combined screen bounds (including offset)
            pixel_x = max(self._screen_x_offset, min(self._screen_x_offset + self._screen_width - 1, pixel_x))
            pixel_y = max(self._screen_y_offset, min(self._screen_y_offset + self._screen_height - 1, pixel_y))

            # Create event source for proper mouse control
            source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)

            # Determine event type based on whether button is held (drag vs move)
            if self._held_button == 'left':
                event_type = kCGEventLeftMouseDragged
                button_num = 0
            elif self._held_button == 'right':
                event_type = kCGEventRightMouseDragged
                button_num = 1
            else:
                # No button held, regular move
                event_type = kCGEventMouseMoved
                button_num = 0

            # Create and post mouse move/drag event
            event = CGEventCreateMouseEvent(
                source,
                event_type,
                (pixel_x, pixel_y),
                button_num
            )
            CGEventPost(kCGHIDEventTap, event)

            log_debug(f"Mouse {'dragged' if self._held_button else 'moved'} to ({pixel_x}, {pixel_y})")
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

            # Query current mouse position in Cocoa coordinates, convert to Quartz
            mouse_loc = NSEvent.mouseLocation()
            quartz_x = int(mouse_loc.x)
            quartz_y = int(self._main_display_height - mouse_loc.y)
            pos = (quartz_x, quartz_y)

            # Create and post mouse down event (hold button)
            down_event = CGEventCreateMouseEvent(
                None,
                down_event_type,
                pos,
                button_num
            )
            CGEventPost(kCGHIDEventTap, down_event)

            # Track held button for drag events
            self._held_button = button

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

            # Query current mouse position in Cocoa coordinates, convert to Quartz
            mouse_loc = NSEvent.mouseLocation()
            quartz_x = int(mouse_loc.x)
            quartz_y = int(self._main_display_height - mouse_loc.y)
            pos = (quartz_x, quartz_y)

            # Create and post mouse up event (release button)
            up_event = CGEventCreateMouseEvent(
                None,
                up_event_type,
                pos,
                button_num
            )
            CGEventPost(kCGHIDEventTap, up_event)

            # Clear held button state
            self._held_button = None

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
        Perform a double mouse click with proper macOS click count and timing.

        Args:
            button: Which mouse button to click

        Returns:
            True if click successful, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        try:
            down_event_type, up_event_type, button_num = self._get_button_event_types(button)

            # Get current mouse position in Cocoa coordinates, convert to Quartz
            mouse_loc = NSEvent.mouseLocation()
            quartz_x = int(mouse_loc.x)
            quartz_y = int(self._main_display_height - mouse_loc.y)
            pos = (quartz_x, quartz_y)

            # First click (clickCount=1)
            down_event = CGEventCreateMouseEvent(None, down_event_type, pos, button_num)
            CGEventSetIntegerValueField(down_event, kCGMouseEventClickState, 1)
            CGEventPost(kCGHIDEventTap, down_event)

            up_event = CGEventCreateMouseEvent(None, up_event_type, pos, button_num)
            CGEventSetIntegerValueField(up_event, kCGMouseEventClickState, 1)
            CGEventPost(kCGHIDEventTap, up_event)

            # Wait between clicks (use 50% of system threshold for reliable detection)
            delay = self._double_click_threshold * 0.25
            time.sleep(delay)

            # Second click (clickCount=2)
            down_event = CGEventCreateMouseEvent(None, down_event_type, pos, button_num)
            CGEventSetIntegerValueField(down_event, kCGMouseEventClickState, 2)
            CGEventPost(kCGHIDEventTap, down_event)

            up_event = CGEventCreateMouseEvent(None, up_event_type, pos, button_num)
            CGEventSetIntegerValueField(up_event, kCGMouseEventClickState, 2)
            CGEventPost(kCGHIDEventTap, up_event)

            log_debug(f"Double-click executed: {button} button (delay: {delay:.3f}s)")
            return True

        except Exception as e:
            log_error("ACT-001", f"Double-click failed: {e}")
            return False
    

    def scroll(self, dx: int = 0, dy: int = 0) -> bool:
        """
        Scroll the mouse wheel (both horizontal and vertical).

        Args:
            dx: Horizontal scroll amount (pixels, positive = right)
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
            scroll_lines_y = dy // 10  # Approximate: 10 pixels = 1 line
            scroll_lines_x = dx // 10

            # Handle small movements (less than 10 pixels)
            if scroll_lines_y == 0 and dy != 0:
                scroll_lines_y = 1 if dy > 0 else -1
            if scroll_lines_x == 0 and dx != 0:
                scroll_lines_x = 1 if dx > 0 else -1

            # Determine if we need 1D or 2D scrolling
            if dx != 0 and dy != 0:
                # 2D scrolling: both horizontal and vertical
                # Note: macOS scroll is inverted (negative = down/right for natural scrolling)
                event = CGEventCreateScrollWheelEvent(
                    None,
                    kCGScrollEventUnitPixel,
                    2,  # Number of wheels (2 for both axes)
                    -scroll_lines_y,  # Vertical (wheel 1)
                    -scroll_lines_x   # Horizontal (wheel 2)
                )
                log_debug(f"Scroll executed: dx={dx}, dy={dy} (lines: x={scroll_lines_x}, y={scroll_lines_y})")
            elif dx != 0:
                # Horizontal scrolling only
                event = CGEventCreateScrollWheelEvent(
                    None,
                    kCGScrollEventUnitPixel,
                    2,  # Need 2 wheels for horizontal
                    0,              # Vertical = 0
                    -scroll_lines_x # Horizontal (wheel 2)
                )
                log_debug(f"Scroll executed: dx={dx} (lines={scroll_lines_x})")
            else:
                # Vertical scrolling only (dy != 0 or both zero)
                event = CGEventCreateScrollWheelEvent(
                    None,
                    kCGScrollEventUnitPixel,
                    1,  # Number of wheels (1 for vertical only)
                    -scroll_lines_y  # Vertical
                )
                log_debug(f"Scroll executed: dy={dy} (lines={scroll_lines_y})")

            CGEventPost(kCGHIDEventTap, event)
            return True

        except Exception as e:
            log_error("ACT-001", f"Scroll failed: {e}")
            return False

    def continuous_zoom(self, dy: int = 0) -> bool:
        """
        Continuous zoom using Command+Plus/Minus keyboard shortcuts.

        Sends Cmd+Plus for zoom in or Cmd+Minus for zoom out. This works in most
        applications (browsers, PDF viewers, image editors, etc.) without requiring
        system accessibility settings.

        Args:
            dy: Vertical zoom amount (pixels, positive = zoom in, negative = zoom out)

        Returns:
            True if zoom successful, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        try:
            # Determine zoom direction
            if dy == 0:
                return True  # No zoom needed

            # Key codes for zoom:
            # 24 = "=" key (same as + on US keyboard, zoom in with Cmd)
            # 27 = "-" key (zoom out with Cmd)
            key_code = 24 if dy > 0 else 27
            zoom_direction = "in" if dy > 0 else "out"

            # Create event source
            source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)

            # Create key down event
            key_down_event = CGEventCreateKeyboardEvent(source, key_code, True)
            CGEventSetFlags(key_down_event, kCGEventFlagMaskCommand)

            # Create key up event
            key_up_event = CGEventCreateKeyboardEvent(source, key_code, False)
            CGEventSetFlags(key_up_event, kCGEventFlagMaskCommand)

            # Post events (down then up = key press)
            CGEventPost(kCGHIDEventTap, key_down_event)
            CGEventPost(kCGHIDEventTap, key_up_event)

            log_debug(f"Continuous zoom executed: zoom {zoom_direction} (dy={dy})")
            return True

        except Exception as e:
            log_error("ACT-001", f"Continuous zoom failed: {e}")
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

    def continuous_volume(self, delta: int = 0) -> bool:
        """
        Continuous volume control using hand movement.

        Uses AppleScript to adjust system volume. Volume ranges from 0-100.

        Args:
            delta: Volume change amount (positive = increase, negative = decrease)

        Returns:
            True if volume change successful, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        try:
            # Get current volume first
            result = subprocess.run(
                ['osascript', '-e', 'output volume of (get volume settings)'],
                capture_output=True,
                text=True,
                timeout=1.0
            )

            if result.returncode != 0:
                log_error("ACT-001", f"Failed to get current volume: {result.stderr}")
                return False

            current_volume = int(result.stdout.strip())

            # Calculate new volume (clamp to 0-100)
            new_volume = max(0, min(100, current_volume + delta))

            # Set new volume
            result = subprocess.run(
                ['osascript', '-e', f'set volume output volume {new_volume}'],
                capture_output=True,
                text=True,
                timeout=1.0
            )

            if result.returncode == 0:
                log_debug(f"Volume changed: {current_volume} -> {new_volume} (delta={delta})")
                return True
            else:
                log_error("ACT-001", f"Failed to set volume: {result.stderr}")
                return False

        except Exception as e:
            log_error("ACT-001", f"Volume control failed: {e}")
            return False

    def continuous_tab(self, direction: int) -> bool:
        """
        Switch browser tabs using Ctrl+Tab (next) or Ctrl+Shift+Tab (previous).

        Uses keyboard shortcuts that work in most browsers and tabbed applications.

        Args:
            direction: Positive = next tab (Ctrl+Tab), Negative = previous tab (Ctrl+Shift+Tab)

        Returns:
            True if tab switch successful, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        try:
            if direction == 0:
                return True  # No tab switch needed

            # Tab key code is 48
            key_code = 48
            tab_direction = "next" if direction > 0 else "previous"

            # Create event source
            source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)

            # Create key down event
            key_down_event = CGEventCreateKeyboardEvent(source, key_code, True)

            # Set modifier flags: Ctrl for next tab, Ctrl+Shift for previous tab
            if direction > 0:
                # Ctrl+Tab for next tab
                CGEventSetFlags(key_down_event, kCGEventFlagMaskControl)
            else:
                # Ctrl+Shift+Tab for previous tab
                CGEventSetFlags(key_down_event, kCGEventFlagMaskControl | kCGEventFlagMaskShift)

            # Create key up event
            key_up_event = CGEventCreateKeyboardEvent(source, key_code, False)

            # Set same modifier flags for key up
            if direction > 0:
                CGEventSetFlags(key_up_event, kCGEventFlagMaskControl)
            else:
                CGEventSetFlags(key_up_event, kCGEventFlagMaskControl | kCGEventFlagMaskShift)

            # Post events (down then up = key press)
            CGEventPost(kCGHIDEventTap, key_down_event)
            CGEventPost(kCGHIDEventTap, key_up_event)

            log_debug(f"Tab switch executed: {tab_direction} tab (direction={direction})")
            return True

        except Exception as e:
            log_error("ACT-001", f"Tab switch failed: {e}")
            return False

    def switch_desktop(self, direction: Literal['left', 'right', 'up', 'down', 'next', 'prev']) -> bool:
        """
        Switch to adjacent virtual desktop using Mission Control.

        Uses osascript subprocess to send Control+Arrow key combinations via System Events.
        This requires Automation permission for System Events but is the only reliable way
        to trigger Mission Control (CGEvent at HID level doesn't reach the Dock/WindowServer).

        Args:
            direction: Direction to switch ('left'/'prev', 'right'/'next', 'up', or 'down')
                      - left/right: Switch between desktops
                      - up: Mission Control (Control+Up)
                      - down: Application Windows (Control+Down)

        Returns:
            True if switch successful, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        try:
            # Map direction to arrow key code
            if direction in ('left', 'prev'):
                key_code = 123  # Left arrow
            elif direction in ('right', 'next'):
                key_code = 124  # Right arrow
            elif direction == 'up':
                key_code = 126  # Up arrow (Mission Control)
            elif direction == 'down':
                key_code = 125  # Down arrow (Application Windows)
            else:
                log_error("ACT-003", f"Invalid desktop switch direction: {direction}")
                return False

            # Use osascript subprocess instead of in-process NSAppleScript
            # This avoids potential blocking/deadlock in daemon thread context
            # and properly triggers Mission Control via System Events
            import subprocess
            script = f'tell application "System Events" to key code {key_code} using control down'

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=1.0  # 2 second timeout
            )

            if result.returncode != 0:
                log_error("ACT-001", f"Desktop switch failed: {result.stderr}")
                return False

            log_info(f"Desktop switch executed via osascript: Control+{direction} (key_code={key_code})")
            return True

        except subprocess.TimeoutExpired:
            log_error("ACT-001", "Desktop switch timed out (System Events not responding)")
            return False
        except Exception as e:
            log_error("ACT-001", f"Desktop switch failed: {e}")
            return False

    def keyboard_shortcut(self, shortcut: str) -> bool:
        """
        Execute keyboard shortcut using Command key combinations.

        Uses CGEvent for keyboard simulation, which works reliably for
        application-level shortcuts like copy/paste/undo (unlike system-level
        shortcuts like Mission Control which require AppleScript).

        Args:
            shortcut: Shortcut string like 'cmd+c', 'cmd+v', 'cmd+z'

        Returns:
            True if shortcut executed successfully, False otherwise
        """
        if not self._initialized:
            log_error("ACT-001", "Adapter not initialized")
            return False

        # Map shortcuts to key codes
        # Key codes: C=8, V=9, Z=6
        shortcut_map = {
            'cmd+c': (8, 'copy'),
            'cmd+v': (9, 'paste'),
            'cmd+z': (6, 'undo'),
        }

        shortcut_lower = shortcut.lower()
        if shortcut_lower not in shortcut_map:
            log_error("ACT-001", f"Unknown keyboard shortcut: {shortcut}")
            return False

        key_code, action_name = shortcut_map[shortcut_lower]

        try:
            # Create event source
            source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)

            # Create key down event with Command modifier
            key_down_event = CGEventCreateKeyboardEvent(source, key_code, True)
            CGEventSetFlags(key_down_event, kCGEventFlagMaskCommand)

            # Create key up event with Command modifier
            key_up_event = CGEventCreateKeyboardEvent(source, key_code, False)
            CGEventSetFlags(key_up_event, kCGEventFlagMaskCommand)

            # Post events (down then up = key press)
            CGEventPost(kCGHIDEventTap, key_down_event)
            CGEventPost(kCGHIDEventTap, key_up_event)

            log_debug(f"Keyboard shortcut executed: {shortcut} ({action_name})")
            return True

        except Exception as e:
            log_error("ACT-001", f"Keyboard shortcut failed: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up macOS adapter resources."""
        log_info("macOS adapter cleaned up")
        self._initialized = False
