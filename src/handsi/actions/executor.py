"""
Thread 4: Action executor thread.

Consumes gesture events from GestureQueue, maps them to actions via YAML config,
and executes actions using OS-specific adapter.
"""

import platform
import threading
import time
from typing import Optional

from handsi.actions.adapters.base import (
    ActionAdapter,
    apply_dead_zone,
    smooth_position,
)
from handsi.actions.state_machine import GestureStateMachine
from handsi.core.bus import GestureEvent, GestureQueue, RuntimeState
from handsi.core.config import ActionConfig, MacOSConfig
from handsi.core.logging import log_debug, log_error, log_info, log_warning


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

        # Relative hand tracking for mouse movement
        self._hand_anchor_pos: Optional[tuple[float, float]] = None  # Where hand was when gesture started
        self._last_mouse_move_time = 0.0  # Track when mouse_move last executed

        # Gesture state tracking for click-and-hold
        self._last_tracked_gesture: Optional[str] = None  # Previous gesture state
        self._held_mouse_button: Optional[str] = None  # Which button is currently held

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
            from handsi.actions.adapters.macos import MacOSAdapter
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
        Tracks gesture state transitions for click-and-hold functionality.
        """
        try:
            # Get gesture event from queue (blocking with timeout)
            gesture_event: Optional[GestureEvent] = self.gesture_queue.get(timeout=0.1)

            if gesture_event is not None:
                # Map gesture to action
                action_name = self._map_gesture_to_action(gesture_event.gesture_name)

                if not action_name:
                    log_debug(f"No action mapped for gesture: {gesture_event.gesture_name}")
                else:
                    # Update hand state from gesture metadata (for mouse movement)
                    self.state_machine.update_hand_state(gesture_event.metadata)

                    # Skip queue-based execution for click - it's handled by state transitions
                    if action_name != "click" and self.state_machine.should_execute(gesture_event, action_name):
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
            # Queue timeout is normal (we use short timeout for responsive state tracking)
            if not self.runtime_state.shutdown_requested:
                log_debug(f"Gesture queue timeout or error: {e}")

        # NEW: Track gesture state transitions for click-and-hold
        # Read current gesture from RuntimeState (updated by inference thread)
        current_gesture = None
        with self.runtime_state.lock:
            current_gesture = self.runtime_state.latest_gesture

        # Detect gesture state transition
        if current_gesture != self._last_tracked_gesture:
            self._handle_gesture_transition(self._last_tracked_gesture, current_gesture)
            self._last_tracked_gesture = current_gesture
        elif current_gesture is not None:
            # Same gesture continuing
            self._handle_gesture_continue(current_gesture)

    def _handle_gesture_transition(self, old_gesture: Optional[str], new_gesture: Optional[str]) -> None:
        """
        Handle gesture state transition (start/end).

        Args:
            old_gesture: Previous gesture (or None)
            new_gesture: New gesture (or None)
        """
        # Handle gesture END
        if old_gesture is not None:
            action = self._map_gesture_to_action(old_gesture)

            if action == "click" and self._held_mouse_button:
                # Release held mouse button
                self.adapter.mouse_up(self._held_mouse_button)  # type: ignore
                log_info(f"Released {self._held_mouse_button} button (gesture '{old_gesture}' ended)")
                self._held_mouse_button = None

        # Handle gesture START
        if new_gesture is not None:
            action = self._map_gesture_to_action(new_gesture)

            if action == "click":
                # Press and hold mouse button
                self.adapter.mouse_down('left')  # type: ignore
                self._held_mouse_button = 'left'
                log_info(f"Pressed left button (gesture '{new_gesture}' started)")
            elif action == "mouse_move":
                # Reset anchor for mouse movement when starting mouse_move gesture
                self._hand_anchor_pos = None

    def _handle_gesture_continue(self, gesture_name: str) -> None:
        """
        Handle gesture continuation (same gesture still active).

        Enables click-and-drag by moving cursor while button is held.

        Args:
            gesture_name: Name of continuing gesture
        """
        action = self._map_gesture_to_action(gesture_name)

        # If holding button and gesture is click, enable drag by moving cursor
        if action == "click" and self._held_mouse_button:
            # Move cursor based on hand position while button is held (drag!)
            self._action_mouse_move()

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
        Execute mouse movement action using relative hand tracking.

        Tracks hand movement delta from an anchor point, preventing cursor
        teleporting when hand reopens at a new position.

        Returns:
            True if successful, False otherwise
        """
        with self.runtime_state.lock:
            hand_pos = self.runtime_state.cursor_position
            hand_scale = self.runtime_state.hand_scale

        if hand_scale == 0.0:
            # No hand detected or invalid scale
            log_debug("Mouse move skipped: hand_scale=0.0")
            return False

        # Apply X-coordinate mirroring if enabled (for natural camera movement)
        if self.action_config.mouse.mirror_x:
            hand_pos = (1.0 - hand_pos[0], hand_pos[1])

        # Check if gesture restarted after being stopped (staleness check)
        current_time = time.time()
        time_since_last_call = current_time - self._last_mouse_move_time
        staleness_threshold = 0.5  # 500ms - gesture is considered "restarted" if not called recently

        if time_since_last_call > staleness_threshold or self._hand_anchor_pos is None:
            # Gesture restarted - set anchor to current hand position
            # Cursor stays where it is (no movement)
            self._hand_anchor_pos = hand_pos
            self._last_mouse_move_time = current_time
            log_debug(f"Gesture restarted after {time_since_last_call:.2f}s - anchored to hand position {hand_pos}")
            return True  # Don't move cursor on first frame after restart

        self._last_mouse_move_time = current_time

        # Calculate hand movement delta from anchor point
        hand_dx = hand_pos[0] - self._hand_anchor_pos[0]
        hand_dy = hand_pos[1] - self._hand_anchor_pos[1]

        log_debug(f"Hand delta from anchor: ({hand_dx:.4f}, {hand_dy:.4f})")

        # Apply dead zone to hand movement delta (ignore small jitters)
        hand_dx, hand_dy = apply_dead_zone(hand_dx, hand_dy, self.action_config.mouse.dead_zone)

        if hand_dx == 0.0 and hand_dy == 0.0:
            # Movement within dead zone, skip
            log_debug(f"Dead zone: hand movement below {self.action_config.mouse.dead_zone:.4f}")
            return True

        # Get current actual mouse cursor position
        current_mouse_x, current_mouse_y = self.adapter.get_mouse_position_normalized()  # type: ignore

        # Apply hand delta to current mouse position
        new_mouse_x = current_mouse_x + hand_dx
        new_mouse_y = current_mouse_y + hand_dy

        # Clamp to screen bounds [0, 1]
        new_mouse_x = max(0.0, min(1.0, new_mouse_x))
        new_mouse_y = max(0.0, min(1.0, new_mouse_y))

        log_debug(f"Moving mouse from ({current_mouse_x:.3f}, {current_mouse_y:.3f}) to ({new_mouse_x:.3f}, {new_mouse_y:.3f})")

        # Move mouse to new absolute position
        result = self.adapter.move_mouse(  # type: ignore
            new_mouse_x,
            new_mouse_y,
            normalized=True,
            relative=False
        )

        # Update anchor to current hand position for continuous tracking
        self._hand_anchor_pos = hand_pos

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
