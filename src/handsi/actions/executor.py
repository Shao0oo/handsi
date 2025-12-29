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
from handsi.core.config import ActionConfig, GestureConfig, MacOSConfig
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
        gesture_config: GestureConfig,
        macos_config: MacOSConfig,
        gesture_queue: GestureQueue,
        runtime_state: RuntimeState,
        name: str = "ActionExecutorThread"
    ):
        super().__init__(name=name, daemon=True)
        self.action_config = action_config
        self.gesture_config = gesture_config
        self.macos_config = macos_config
        self.gesture_queue = gesture_queue
        self.runtime_state = runtime_state

        # OS-specific adapter
        self.adapter: Optional[ActionAdapter] = None

        # State machine for debouncing and continuous gestures
        self.state_machine = GestureStateMachine(
            runtime_state=runtime_state,
            debounce_ms=gesture_config.debounce_ms,
            latch_cooldown_ms=gesture_config.latch_cooldown_ms
        )

        # Relative hand tracking for mouse movement
        self._hand_anchor_pos: Optional[tuple[float, float]] = None  # Where hand was when gesture started
        self._last_mouse_move_time = 0.0  # Track when mouse_move last executed

        # Gesture state tracking for click-and-hold
        self._last_tracked_gesture: Optional[str] = None  # Previous gesture state
        self._held_mouse_button: Optional[str] = None  # Which button is currently held

        # Smooth interpolation state
        self._interpolation_target_pos: Optional[tuple[float, float]] = None  # Target hand position
        self._interpolation_last_update_time: float = 0.0  # When target was last updated
        self._interpolation_rate: float = action_config.mouse.interpolation_rate  # Hz - from config
        self._interpolation_enabled: bool = False  # Whether interpolation is active
        self._interpolation_lock = threading.Lock()  # Thread-safe access to interpolation state

    def run(self) -> None:
        """Main action executor loop."""
        log_info(f"{self.name} started")

        # Initialize OS adapter
        if not self._initialize_adapter():
            log_error("ACT-004", "Failed to initialize action adapter")
            return

        # Start interpolation timer thread
        interpolation_thread = threading.Thread(
            target=self._interpolation_loop,
            name="InterpolationThread",
            daemon=True
        )
        interpolation_thread.start()

        try:
            while not self.runtime_state.shutdown_requested:
                self._process_gesture()

        except Exception as e:
            log_error("ACT-001", f"Unexpected error in action executor loop: {e}")

        finally:
            if self.adapter:
                self.adapter.cleanup()
            log_info(f"{self.name} stopped")

    def _interpolation_loop(self) -> None:
        """
        Background thread that smoothly interpolates cursor position at high frequency (60 Hz).

        Runs independently of gesture detection rate (10 Hz), providing smooth cursor
        movement by interpolating between gesture updates.
        """
        log_info("Interpolation thread started")
        sleep_time = 1.0 / self._interpolation_rate

        try:
            while not self.runtime_state.shutdown_requested:
                # Check if interpolation is enabled
                with self._interpolation_lock:
                    enabled = self._interpolation_enabled
                    target_pos = self._interpolation_target_pos
                    last_update_time = self._interpolation_last_update_time

                if not enabled or target_pos is None:
                    # No active mouse_move gesture, sleep and continue
                    time.sleep(sleep_time)
                    continue

                # Calculate how stale the target position is
                current_time = time.time()
                staleness = current_time - last_update_time

                # If target is too stale (>500ms), stop interpolation
                # This prevents cursor from moving when hand is no longer detected
                if staleness > 0.5:
                    with self._interpolation_lock:
                        self._interpolation_enabled = False
                    log_debug("Interpolation disabled due to stale target")
                    time.sleep(sleep_time)
                    continue

                # Perform smooth cursor movement
                self._interpolate_cursor_to_target(target_pos)

                # Sleep to maintain 60 Hz rate
                time.sleep(sleep_time)

        except Exception as e:
            log_error("ACT-005", f"Interpolation loop error: {e}")
        finally:
            log_info("Interpolation thread stopped")

    def _interpolate_cursor_to_target(self, target_hand_pos: tuple[float, float]) -> None:
        """
        Move cursor smoothly toward target hand position.

        Uses exponential smoothing (EMA) to create natural, responsive movement.

        Args:
            target_hand_pos: Target hand position (normalized, 0-1)
        """
        if not self.adapter:
            return

        # Get hand scale for distance normalization
        with self.runtime_state.lock:
            hand_scale = self.runtime_state.hand_scale

        if hand_scale <= 0.0:
            # No valid hand scale, skip movement
            return

        # Apply X-coordinate mirroring if enabled
        if self.action_config.mouse.mirror_x:
            target_hand_pos = (1.0 - target_hand_pos[0], target_hand_pos[1])

        # Initialize anchor on first call
        if self._hand_anchor_pos is None:
            self._hand_anchor_pos = target_hand_pos
            log_debug(f"Interpolation anchor initialized to {target_hand_pos}")
            return

        # Calculate hand movement delta from anchor (in screen coordinates)
        hand_dx = target_hand_pos[0] - self._hand_anchor_pos[0]
        hand_dy = target_hand_pos[1] - self._hand_anchor_pos[1]

        # NORMALIZE by hand scale: divide by hand_scale to make movement distance-invariant
        # When hand is far (small scale), same screen delta = larger physical movement
        # When hand is close (large scale), same screen delta = smaller physical movement
        # Dividing by scale compensates: far hand gets boosted, close hand gets reduced
        hand_dx = hand_dx / hand_scale
        hand_dy = hand_dy / hand_scale

        # Apply dead zone (ignore tiny jitters)
        from handsi.actions.adapters.base import apply_dead_zone
        hand_dx, hand_dy = apply_dead_zone(hand_dx, hand_dy, self.action_config.mouse.dead_zone)

        if hand_dx == 0.0 and hand_dy == 0.0:
            return

        # Get current mouse position
        current_mouse_x, current_mouse_y = self.adapter.get_mouse_position_normalized()  # type: ignore

        # Calculate target mouse position (anchor + delta)
        target_mouse_x = current_mouse_x + hand_dx
        target_mouse_y = current_mouse_y + hand_dy

        # Clamp to screen bounds
        target_mouse_x = max(0.0, min(1.0, target_mouse_x))
        target_mouse_y = max(0.0, min(1.0, target_mouse_y))

        # Apply exponential moving average (EMA) for smoothness
        # Lower alpha = more smoothing (slower), higher alpha = less smoothing (faster)
        alpha = 1.0 - self.action_config.mouse.smoothing_factor
        new_mouse_x = current_mouse_x + alpha * (target_mouse_x - current_mouse_x) * self.action_config.mouse.sensitivity
        new_mouse_y = current_mouse_y + alpha * (target_mouse_y - current_mouse_y) * self.action_config.mouse.sensitivity

        # Move mouse
        self.adapter.move_mouse(  # type: ignore
            new_mouse_x,
            new_mouse_y,
            normalized=True,
            relative=False
        )

        # Update anchor to current hand position for next interpolation
        self._hand_anchor_pos = target_hand_pos

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
            gesture_event: Optional[GestureEvent] = self.gesture_queue.get(timeout=0.01)

            if gesture_event is not None:
                # Map gesture to action
                action_name = self._map_gesture_to_action(gesture_event.gesture_name)

                if not action_name:
                    log_debug(f"No action mapped for gesture: {gesture_event.gesture_name}")
                else:
                    # Update hand state from gesture metadata (for mouse movement and click-and-drag)
                    self.state_machine.update_hand_state(gesture_event.metadata)

                    # Skip queue-based execution for click - it's handled by state transitions
                    # But still update hand state above to enable cursor movement during drag
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
            # Check latch for state transitions (click, mouse_move)
            if current_gesture is not None:
                action = self._map_gesture_to_action(current_gesture)
                if action and not self.state_machine.is_action_allowed(action):
                    # Latch blocks this action - don't process transition
                    log_debug(f"Gesture transition blocked by latch: {current_gesture} -> {action}")
                    return

            self._handle_gesture_transition(self._last_tracked_gesture, current_gesture)
            self._last_tracked_gesture = current_gesture
        elif current_gesture is not None:
            # Same gesture continuing - check latch before continuing
            action = self._map_gesture_to_action(current_gesture)
            if action and not self.state_machine.is_action_allowed(action):
                # Latch blocks this action - don't continue gesture
                return

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
                # Disable interpolation when click gesture ends
                with self._interpolation_lock:
                    self._interpolation_enabled = False
            elif action == "mouse_move":
                # Disable interpolation when mouse_move gesture ends
                with self._interpolation_lock:
                    self._interpolation_enabled = False
                log_debug("Interpolation disabled (gesture ended)")

        # Handle gesture START
        if new_gesture is not None:
            action = self._map_gesture_to_action(new_gesture)

            if action == "click":
                # Press and hold mouse button
                self.adapter.mouse_down('left')  # type: ignore
                self._held_mouse_button = 'left'
                log_info(f"Pressed left button (gesture '{new_gesture}' started)")
                # Enable interpolation for click-and-drag
                with self._interpolation_lock:
                    self._interpolation_enabled = True
                self._hand_anchor_pos = None  # Reset anchor for drag movement
            elif action == "mouse_move":
                # Reset anchor for mouse movement when starting mouse_move gesture
                self._hand_anchor_pos = None
                # Enable interpolation for smooth cursor movement
                with self._interpolation_lock:
                    self._interpolation_enabled = True
                log_debug("Interpolation enabled (mouse_move started)")

    def _handle_gesture_continue(self, gesture_name: str) -> None:
        """
        Handle gesture continuation (same gesture still active).

        Updates interpolation target for mouse_move or enables click-and-drag.

        Args:
            gesture_name: Name of continuing gesture
        """
        action = self._map_gesture_to_action(gesture_name)

        # Update interpolation target for mouse_move gesture
        if action == "mouse_move":
            self._update_interpolation_target()
        # If holding button and gesture is click, enable drag by moving cursor
        elif action == "click" and self._held_mouse_button:
            # Update interpolation target to enable drag while button is held
            self._update_interpolation_target()

    def _update_interpolation_target(self) -> None:
        """
        Update the interpolation target position from RuntimeState.

        Called when mouse_move gesture continues, providing new hand position
        for the interpolation thread to smoothly move toward.
        """
        with self.runtime_state.lock:
            hand_pos = self.runtime_state.cursor_position
            hand_scale = self.runtime_state.hand_scale

        if hand_scale == 0.0:
            # No valid hand detected
            return

        # Update interpolation target and timestamp
        with self._interpolation_lock:
            self._interpolation_target_pos = hand_pos
            self._interpolation_last_update_time = time.time()
            # Ensure interpolation is enabled (may have been disabled due to staleness)
            self._interpolation_enabled = True

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
            # For mouse_move, just update the interpolation target
            # The interpolation thread will handle smooth movement
            self._update_interpolation_target()
            return True
        elif action_name == "click":
            print(f"Executing click with button: {gesture_event.metadata.get('button', 'left')}")
            return self._action_click()
        elif action_name == "double_click":
            return self._action_double_click()
        elif action_name == "right_click":
            return self._action_click(button="right")
        elif action_name == "scroll_down":
            return self._action_scroll(direction='down')
        elif action_name == "scroll_up":
            return self._action_scroll(direction='up')
        elif action_name == "zoom_in":
            return self._action_zoom(direction='in')
        elif action_name == "zoom_out":
            return self._action_zoom(direction='out')
        elif action_name == "switch_desktop":
            # Extract direction from gesture metadata
            direction = gesture_event.metadata.get('direction')
            if not direction:
                log_error("ACT-003", "switch_desktop action missing 'direction' in metadata")
                return False
            return self._action_switch_desktop(direction=direction)
        elif action_name == "enable_latch":
            return self._action_enable_latch()
        elif action_name == "disable_latch":
            print(f"Executing disable latch action: {action_name}")
            return self._action_disable_latch()
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


    def _action_double_click(self, button: str = 'left') -> bool:
        """
        Execute mouse click action.

        Args:
            button: Which button to click

        Returns:
            True if successful, False otherwise
        """
        return self.adapter.double_click(button=button)  # type: ignore

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

    def _action_enable_latch(self) -> bool:
        """
        Enable latch state (turn on gesture control).

        Returns:
            True if successful, False if in cooldown
        """
        return self.state_machine.enable_latch()

    def _action_disable_latch(self) -> bool:
        """
        Disable latch state (turn off gesture control).

        Returns:
            True if successful, False if in cooldown
        """
        return self.state_machine.disable_latch()
