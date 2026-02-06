"""
Platform-agnostic IPC adapter.

All actions are sent to Rust via IPC. NO OS-specific code here.
This adapter is the single interface for all action execution.

Rust handles ALL platform-specific operations including:
- Screen dimension queries
- Coordinate conversion (normalized ↔ pixels)
- Multi-monitor support
- OS-specific APIs (CGEvent, Win32, X11, etc.)
"""

import json
from typing import Literal, Optional

from handsi.core.logging import log_debug


class IPCAdapter:
    """
    Action adapter that sends all operations to Rust via IPC.

    This adapter is platform-agnostic - all OS-specific code
    lives in the Rust frontend (src-tauri/src/adapters/).

    Communication uses fire-and-forget JSON messages to stdout,
    which Rust reads and executes via the platform adapter.

    All coordinates sent to Rust are normalized [0, 1] and Rust
    handles conversion to pixels based on screen dimensions.
    """

    def __init__(self):
        self._initialized = False

        # Track last mouse position (normalized) for button events (click, mouse_down, etc.)
        # Updated by move_mouse() calls; used to send position with button actions
        self._last_mouse_x = 0.5  # Center of screen
        self._last_mouse_y = 0.5

    def initialize(self) -> bool:
        """Initialize the adapter."""
        self._initialized = True
        log_debug("IPCAdapter initialized")
        return True

    def check_permissions(self) -> bool:
        """
        Check if necessary OS permissions are granted.

        Note: Actual permission checking is done by Rust.
        This always returns True since we can't check from Python.
        """
        return True

    def _send_action(self, action: dict) -> bool:
        """
        Send action to Rust (fire-and-forget).

        Args:
            action: Dictionary with action type and parameters

        Returns:
            True if action was sent successfully, False otherwise
        """
        try:
            action["type"] = "action"
            print(json.dumps(action), flush=True)
            return True
        except Exception as e:
            log_debug(f"Failed to send action: {e}")
            return False

    # =========================================================================
    # Mouse Actions
    # =========================================================================

    def move_mouse(
        self,
        x: float,
        y: float,
        normalized: bool = False,
        relative: bool = False
    ) -> bool:
        """
        Move mouse cursor to specified position.

        Args:
            x: X coordinate (normalized 0-1 if normalized=True, else pixels)
            y: Y coordinate (normalized 0-1 if normalized=True, else pixels)
            normalized: If True, x/y are in range [0, 1]
            relative: Ignored (for interface compatibility)

        Returns:
            True if action was sent successfully
        """
        # If normalized, track position and send directly to Rust
        # Rust handles conversion to pixels based on screen dimensions
        if normalized:
            self._last_mouse_x = x
            self._last_mouse_y = y
            return self._send_action({
                "action": "mouse_move_normalized",
                "x": float(x),
                "y": float(y)
            })
        else:
            # Pixel coordinates - less common, used by some handlers
            # TODO: Should we track normalized position here too?
            return self._send_action({
                "action": "mouse_move",
                "x": float(x),
                "y": float(y)
            })

    def move_mouse_relative(self, dx: float, dy: float) -> bool:
        """
        Move mouse cursor by delta (relative movement).

        Rust uses internally tracked position and applies the delta.
        Call reset_cursor_tracking() at gesture start to sync with actual OS position.

        Args:
            dx: Delta X in normalized coordinates
            dy: Delta Y in normalized coordinates

        Returns:
            True if action was sent successfully
        """
        return self._send_action({
            "action": "mouse_move_relative_normalized",
            "dx": float(dx),
            "dy": float(dy)
        })

    def reset_cursor_tracking(self) -> bool:
        """
        Reset Rust's cursor tracking to actual OS position.

        Call at gesture start to prevent teleporting after manual mouse movement.
        Rust will query the actual OS cursor position and use it as the starting
        point for subsequent relative moves.

        Returns:
            True if action was sent successfully
        """
        return self._send_action({
            "action": "reset_cursor_tracking"
        })

    def mouse_down(self, button: Literal['left', 'right', 'middle'] = 'left') -> bool:
        """
        Press and hold mouse button without releasing.

        Args:
            button: Which mouse button to press

        Returns:
            True if action was sent successfully
        """
        btn_map = {'left': 0, 'right': 1, 'middle': 2}
        return self._send_action({
            "action": "mouse_down_normalized",
            "x": self._last_mouse_x,  # Use last known normalized position
            "y": self._last_mouse_y,
            "button": btn_map[button]
        })

    def mouse_up(self, button: Literal['left', 'right', 'middle'] = 'left') -> bool:
        """
        Release held mouse button.

        Args:
            button: Which mouse button to release

        Returns:
            True if action was sent successfully
        """
        btn_map = {'left': 0, 'right': 1, 'middle': 2}
        return self._send_action({
            "action": "mouse_up_normalized",
            "x": self._last_mouse_x,  # Use last known normalized position
            "y": self._last_mouse_y,
            "button": btn_map[button]
        })

    def click(self, button: Literal['left', 'right', 'middle'] = 'left') -> bool:
        """
        Perform a mouse click (press and release).

        Args:
            button: Which mouse button to click

        Returns:
            True if action was sent successfully
        """
        btn_map = {'left': 0, 'right': 1, 'middle': 2}
        return self._send_action({
            "action": "click_normalized",
            "x": self._last_mouse_x,  # Use last known normalized position
            "y": self._last_mouse_y,
            "button": btn_map[button]
        })

    def double_click(self, button: Literal['left', 'right', 'middle'] = 'left') -> bool:
        """
        Perform a double-click.

        Args:
            button: Which mouse button to double-click

        Returns:
            True if action was sent successfully
        """
        btn_map = {'left': 0, 'right': 1, 'middle': 2}
        return self._send_action({
            "action": "double_click_normalized",
            "x": self._last_mouse_x,  # Use last known normalized position
            "y": self._last_mouse_y,
            "button": btn_map[button]
        })

    # =========================================================================
    # Scroll Actions
    # =========================================================================

    def scroll(self, dx: int = 0, dy: int = 0) -> bool:
        """
        Scroll the mouse wheel.

        Args:
            dx: Horizontal scroll amount (pixels)
            dy: Vertical scroll amount (pixels, positive = down)

        Returns:
            True if action was sent successfully
        """
        return self._send_action({
            "action": "scroll",
            "dx": int(dx),
            "dy": int(dy)
        })

    # =========================================================================
    # Keyboard Actions
    # =========================================================================

    def keyboard_shortcut(self, shortcut: str) -> bool:
        """
        Execute keyboard shortcut using modifier key combinations.

        Args:
            shortcut: Shortcut string like 'cmd+c', 'cmd+v', 'ctrl+z'

        Returns:
            True if action was sent successfully
        """
        return self._send_action({
            "action": "keyboard_shortcut",
            "shortcut": shortcut
        })

    def key_press(self, key_code: int, modifiers: int = 0) -> bool:
        """
        Send a key press event with optional modifiers.

        Args:
            key_code: Virtual key code
            modifiers: Modifier flags

        Returns:
            True if action was sent successfully
        """
        return self._send_action({
            "action": "key_press",
            "key_code": key_code,
            "modifiers": modifiers
        })

    # =========================================================================
    # Desktop/Workspace Actions
    # =========================================================================

    def switch_desktop(
        self,
        direction: Literal['left', 'right', 'up', 'down', 'next', 'prev']
    ) -> bool:
        """
        Switch to adjacent virtual desktop/workspace.

        Args:
            direction: Direction to switch

        Returns:
            True if action was sent successfully
        """
        return self._send_action({
            "action": "switch_desktop",
            "direction": direction
        })

    def continuous_tab(self, direction: int = 0) -> bool:
        """
        Switch browser tabs using Ctrl+Tab or Ctrl+Shift+Tab.

        Args:
            direction: Positive = next tab, negative = previous tab

        Returns:
            True if action was sent successfully
        """
        shortcut = "ctrl+tab" if direction >= 0 else "ctrl+shift+tab"
        return self.keyboard_shortcut(shortcut)

    # =========================================================================
    # Volume Actions
    # =========================================================================

    def continuous_volume(self, delta: int = 0) -> bool:
        """
        Adjust system volume by delta amount.

        Args:
            delta: Volume change (-100 to +100)

        Returns:
            True if action was sent successfully
        """
        return self._send_action({
            "action": "set_volume",
            "delta": int(delta)
        })

    # =========================================================================
    # Zoom Actions
    # =========================================================================

    def zoom(self, direction: Literal['in', 'out'], step: float = 0.1) -> bool:
        """
        Zoom in or out (system-wide zoom or browser zoom).

        Args:
            direction: 'in' to zoom in, 'out' to zoom out
            step: Zoom increment (e.g., 0.1 = 10%)

        Returns:
            True if action was sent successfully
        """
        return self._send_action({
            "action": "zoom",
            "direction": direction,
            "step": float(step)
        })

    def continuous_zoom(self, dy: int = 0) -> bool:
        """
        Continuous zoom based on movement direction.

        Args:
            dy: Positive = zoom in, negative = zoom out

        Returns:
            True if action was sent successfully
        """
        direction = "in" if dy > 0 else "out"
        return self._send_action({
            "action": "zoom",
            "direction": direction,
            "step": 0.1
        })

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def cleanup(self) -> None:
        """Clean up adapter resources."""
        pass
