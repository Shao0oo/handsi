"""
Thread 4: Action executor thread.

Consumes gesture events from GestureQueue, maps them to actions via YAML config,
and executes actions using OS-specific adapter.
"""

import platform
import threading
import time
from typing import Optional

from airdesk.actions.adapters.base import (
    ActionAdapter,
    apply_dead_zone,
    smooth_position,
)
from airdesk.actions.state_machine import GestureStateMachine
from airdesk.core.bus import GestureEvent, GestureQueue, RuntimeState
from airdesk.core.config import ActionConfig, MacOSConfig
from airdesk.core.logging import log_debug, log_error, log_info, log_warning


class ActionExecutorThread(threading.Thread):
    """
    Thread 4: Action Executor.

    Responsibilities:
    - Pop gesture events from GestureQueue
    - Map gestures to actions via config
    - Execute actions via OS-specific adapter
    - Update RuntimeState with latest action
    - Apply debouncing and state machine logic
    """

    def __init__(
        self,
        action_config: ActionConfig,
        macos_config: MacOSConfig,
        gesture_queue: GestureQueue,
        runtime_state: RuntimeState,
        name: str = "ActionExecutorThread"
    ):
        super().__init__(name=name, daemon=True)
        self.action_config = action_config
        self.macos_config = macos_config
        self.gesture_queue = gesture_queue
        self.runtime_state = runtime_state

        # OS-specific adapter
        self.adapter: Optional[ActionAdapter] = None

        # State machine for debouncing and continuous gestures
        self.state_machine = GestureStateMachine(
            runtime_state=runtime_state,
            debounce_ms=300,  # From config (could parameterize)
            latch_cooldown_ms=500
        )

        # Smoothed cursor position for mouse movement
        self._smoothed_cursor = (0.5, 0.5)  # Start at screen center

    def run(self) -> None:
        """Main action executor loop."""
        log_info(f"{self.name} started")

        # Initialize OS adapter
        if not self._initialize_adapter():
            log_error("ACT-004", "Failed to initialize action adapter")
            return

        try:
            while not self.runtime_state.shutdown_requested:
                self._process_gesture()

        except Exception as e:
            log_error("ACT-001", f"Unexpected error in action executor loop: {e}")

        finally:
            if self.adapter:
                self.adapter.cleanup()
            log_info(f"{self.name} stopped")

    def _initialize_adapter(self) -> bool:
        """
        Initialize OS-specific action adapter.

        Returns:
            True if initialization successful, False otherwise
        """
        system = platform.system()

        if system == "Darwin":
            # macOS
            from airdesk.actions.adapters.macos import MacOSAdapter
            self.adapter = MacOSAdapter()
        elif system == "Linux":
            # Linux (not yet implemented)
            log_error("ACT-004", "Linux adapter not yet implemented")
            return False
        elif system == "Windows":
            # Windows (not yet implemented)
            log_error("ACT-004", "Windows adapter not yet implemented")
            return False
        else:
            log_error("ACT-004", f"Unsupported platform: {system}")
            return False

        # Initialize adapter
        if not self.adapter.initialize():
            return False

        # Check permissions
        if self.macos_config.accessibility_check:
            self.adapter.check_permissions()

        return True

    def _process_gesture(self) -> None:
        """
        Process a single gesture event from the queue.

        Maps gesture to action and executes via adapter.
        """
        try:
            # Get gesture event from queue (blocking with timeout)
            gesture_event: Optional[GestureEvent] = self.gesture_queue.get(timeout=1.0)

            if gesture_event is None:
                return

            # self.runtime_state = gesture_event.metadata

            # Map gesture to action
            action_name = self._map_gesture_to_action(gesture_event.gesture_name)

            if not action_name:
                log_debug(f"No action mapped for gesture: {gesture_event.gesture_name}")
                return

            # Update hand state from gesture metadata (for mouse movement)
            self.state_machine.update_hand_state(gesture_event.metadata)

            # Check if action should execute (debouncing, latch, etc.)
            if not self.state_machine.should_execute(gesture_event, action_name):
                return

            # Execute action
            success = self._execute_action(action_name, gesture_event)

            if success:
                # Update RuntimeState with latest action
                with self.runtime_state.lock:
                    self.runtime_state.latest_action = action_name
                    self.runtime_state.latest_action_time = time.time()
                    self.runtime_state.actions_executed += 1
                    self.runtime_state.mark_gesture_detected()

                log_info(
                    f"Action executed: {action_name} "
                    f"(from gesture: {gesture_event.gesture_name}, "
                    f"confidence: {gesture_event.confidence:.2f})"
                )
            else:
                log_error("ACT-002", f"Action: {success}")

        except Exception as e:
            # Queue timeout is normal during shutdown
            if not self.runtime_state.shutdown_requested:
                log_debug(f"Gesture queue timeout or error: {e}")

    def _map_gesture_to_action(self, gesture_name: str) -> Optional[str]:
        """
        Map gesture name to action name via config.

        Args:
            gesture_name: Name of detected gesture

        Returns:
            Action name, or None if no mapping exists
        """
        return self.action_config.mappings.get(gesture_name)

    def _execute_action(self, action_name: str, gesture_event: GestureEvent) -> bool:
        """
        Execute a specific action via the adapter.

        Args:
            action_name: Name of action to execute
            gesture_event: The gesture event that triggered this action

        Returns:
            True if action executed successfully, False otherwise
        """
        if not self.adapter:
            log_error("ACT-004", "Adapter not initialized")
            return False

        # Route to appropriate action handler
        if action_name == "mouse_move":
            print(f"Executing mouse move with hand position: {gesture_event.metadata['position']}")
            return self._action_mouse_move()
        elif action_name == "click":
            print(f"Executing click with button: {gesture_event.metadata.get('button', 'left')}")
            return self._action_click()
        elif action_name == "scroll_down":
            return self._action_scroll(direction='down')
        elif action_name == "scroll_up":
            return self._action_scroll(direction='up')
        elif action_name == "zoom_in":
            return self._action_zoom(direction='in')
        elif action_name == "zoom_out":
            return self._action_zoom(direction='out')
        elif action_name == "switch_desktop_left":
            return self._action_switch_desktop(direction='left')
        elif action_name == "switch_desktop_right":
            return self._action_switch_desktop(direction='right')
        else:
            log_warning("ACT-003", f"Unknown action: {action_name}")
            return False

    # Action handlers

    def _action_mouse_move(self) -> bool:
        """
        Execute mouse movement action using hand position.

        Returns:
            True if successful, False otherwise
        """
        with self.runtime_state.lock:
            target_pos = self.runtime_state.cursor_position
            hand_scale = self.runtime_state.hand_scale

        if hand_scale == 0.0:
            # No hand detected or invalid scale
            log_debug("Mouse move skipped: hand_scale=0.0")
            return False

        # Apply X-coordinate mirroring if enabled (for natural camera movement)
        if self.action_config.mouse.mirror_x:
            target_pos = (1.0 - target_pos[0], target_pos[1])

        log_debug(f"Hand position: {target_pos}, hand_scale: {hand_scale:.3f}")

        # Store previous smoothed position (for delta calculation)
        previous_pos = self._smoothed_cursor

        # Apply smoothing
        self._smoothed_cursor = smooth_position(
            self._smoothed_cursor,
            target_pos,
            self.action_config.mouse.smoothing_factor
        )

        log_debug(f"Smoothed position: {self._smoothed_cursor}")

        # Calculate delta between current and previous smoothed positions
        # This measures actual cursor movement, not convergence error
        dx = self._smoothed_cursor[0] - previous_pos[0]
        dy = self._smoothed_cursor[1] - previous_pos[1]

        print(f"Mouse move delta: ({dx:.4f}, {dy:.4f})")

        # Apply dead zone (ignore small jitters)
        dx, dy = apply_dead_zone(dx, dy, self.action_config.mouse.dead_zone)

        if dx == 0.0 and dy == 0.0:
            # Movement within dead zone, skip
            log_debug(f"Dead zone: skipped (delta magnitude below {self.action_config.mouse.dead_zone:.4f})")
            return True

        # Move mouse (normalized coordinates)
        log_debug(f"Moving mouse to normalized ({self._smoothed_cursor[0]:.3f}, {self._smoothed_cursor[1]:.3f})")
        result = self.adapter.move_mouse( # type: ignore
            self._smoothed_cursor[0],
            self._smoothed_cursor[1],
            normalized=True,
            relative=False
        )
        log_debug(f"Mouse move result: {result}")
        return result

    def _action_click(self, button: str = 'left') -> bool:
        """
        Execute mouse click action.

        Args:
            button: Which button to click

        Returns:
            True if successful, False otherwise
        """
        return self.adapter.click(button=button)  # type: ignore

    def _action_scroll(self, direction: str) -> bool:
        """
        Execute scroll action.

        Args:
            direction: 'up' or 'down'

        Returns:
            True if successful, False otherwise
        """
        scroll_speed = self.macos_config.scroll_speed

        if direction == 'down':
            dy = scroll_speed
        elif direction == 'up':
            dy = -scroll_speed
        else:
            log_error("ACT-003", f"Invalid scroll direction: {direction}")
            return False

        return self.adapter.scroll(dx=0, dy=dy) # type: ignore

    def _action_zoom(self, direction: str) -> bool:
        """
        Execute zoom action.

        Args:
            direction: 'in' or 'out'

        Returns:
            True if successful, False otherwise
        """
        zoom_step = self.macos_config.zoom_step
        return self.adapter.zoom(direction=direction, step=zoom_step)  # type: ignore

    def _action_switch_desktop(self, direction: str) -> bool:
        """
        Execute desktop switch action.

        Args:
            direction: 'left' or 'right'

        Returns:
            True if successful, False otherwise
        """
        return self.adapter.switch_desktop(direction=direction)  # type: ignore
