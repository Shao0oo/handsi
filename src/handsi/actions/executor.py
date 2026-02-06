"""
Thread 4: Action executor thread.

Consumes gesture events from GestureQueue, maps them to actions via YAML config,
and executes actions using OS-specific adapter.

This is the slim orchestrator that delegates to specialized handler classes.
"""

import threading
import time
from typing import Dict, Optional, Union

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.adapters.ipc import IPCAdapter
from handsi.actions.handlers.alert import CompositeAlertHandler
from handsi.actions.handlers.base import ActionHandler
from handsi.core.types import ActionName
from handsi.actions.handlers.click import ClickHandler, DoubleClickHandler, RightClickHandler
from handsi.actions.handlers.desktop import SwitchDesktopHandler
from handsi.actions.handlers.keyboard import CopyHandler, PasteHandler, UndoHandler
from handsi.actions.handlers.latch import DisableLatchHandler, EnableLatchHandler
from handsi.actions.handlers.mouse import MouseMoveHandler
from handsi.actions.handlers.scroll import ContinuousScrollHandler, ScrollStepHandler
from handsi.actions.handlers.tab import ContinuousTabHandler
from handsi.actions.handlers.volume import ContinuousVolumeHandler
from handsi.actions.handlers.zoom import ContinuousZoomHandler, ZoomStepHandler
from handsi.actions.interpolation import CursorInterpolator
from handsi.actions.momentum import ScrollMomentum
from handsi.actions.state_machine import GestureStateMachine
from handsi.core.bus import GestureEvent, GestureQueue, RuntimeState
from handsi.core.config import ActionConfig, GestureConfig, MacOSConfig
from handsi.core.logging import log_debug, log_error, log_info, log_warning


class ActionExecutorThread(threading.Thread):
    """
    Thread 4: Action Executor.

    Orchestrates gesture processing and action execution by:
    - Consuming gesture events from GestureQueue
    - Mapping gestures to actions via config
    - Delegating to specialized handler classes
    - Managing gesture lifecycle (start/continue/end)
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

        # OS-specific adapter (initialized in run())
        self.adapter: Optional[ActionAdapter] = None

        # State machine for debouncing and latch control
        self.state_machine = GestureStateMachine(
            runtime_state=runtime_state,
            debounce_ms=gesture_config.debounce_ms,
            latch_cooldown_ms=gesture_config.latch_cooldown_ms
        )

        # Components (initialized in run())
        self.interpolator: Optional[CursorInterpolator] = None
        self.momentum: Optional[ScrollMomentum] = None
        self.handlers: Dict[ActionName, ActionHandler] = {}

        # Gesture state tracking
        self._last_tracked_gesture: Optional[str] = None

    def run(self) -> None:
        """Main action executor loop."""
        log_info(f"{self.name} started")

        # Initialize adapter
        if not self._initialize_adapter():
            log_error("ACT-004", "Failed to initialize action adapter")
            return

        # Initialize components
        self._initialize_components()

        # Start background threads
        self.interpolator.start()
        self.momentum.start()

        try:
            while not self.runtime_state.shutdown_requested:
                self._process_gesture()

        except Exception as e:
            log_error("ACT-001", f"Unexpected error in action executor loop: {e}")

        finally:
            # Clean up all handlers (releases held buttons, etc.)
            for handler in self.handlers.values():
                try:
                    handler.cleanup()
                except Exception as e:
                    log_error("ACT-007", f"Handler cleanup failed: {e}")

            if self.adapter:
                self.adapter.cleanup()
            log_info(f"{self.name} stopped")

    def _initialize_adapter(self) -> bool:
        """
        Initialize IPC action adapter.

        Returns:
            True if initialization successful, False otherwise
        """
        # Use IPC adapter to send all actions to Rust
        self.adapter = IPCAdapter()

        # IPC adapter doesn't need initialization or permission checks
        # (Rust side handles all OS-specific operations and has TCC permissions)
        log_info("Action executor initialized with IPC adapter")

        return True

    def _initialize_components(self) -> None:
        """Initialize interpolator, momentum, and handlers."""
        # Create interpolator for smooth cursor movement
        self.interpolator = CursorInterpolator.from_mouse_config(
            self.adapter,
            self.action_config.mouse,
            self.runtime_state
        )

        # Create momentum for kinetic scrolling
        self.momentum = ScrollMomentum.from_scroll_config(
            self.adapter,
            self.action_config.scroll,
            self.runtime_state
        )

        # Create handlers
        self.handlers = self._create_handlers()

    def _create_handlers(self) -> Dict[ActionName, ActionHandler]:
        """Create all action handlers."""
        return {
            # Mouse movement
            ActionName.MOUSE_MOVE: MouseMoveHandler(
                self.adapter,
                self.runtime_state,
                self.interpolator
            ),

            # Click actions
            ActionName.CLICK: ClickHandler(
                self.adapter,
                self.runtime_state,
                self.interpolator,
                button='left'
            ),
            ActionName.DOUBLE_CLICK: DoubleClickHandler(
                self.adapter,
                self.runtime_state,
                button='left'
            ),
            ActionName.RIGHT_CLICK: RightClickHandler(
                self.adapter,
                self.runtime_state
            ),

            # Scroll actions
            ActionName.SCROLL_UP: ScrollStepHandler(
                self.adapter,
                self.runtime_state,
                self.action_config.scroll,
                direction='up'
            ),
            ActionName.SCROLL_DOWN: ScrollStepHandler(
                self.adapter,
                self.runtime_state,
                self.action_config.scroll,
                direction='down'
            ),
            ActionName.CONTINUOUS_SCROLL: ContinuousScrollHandler(
                self.adapter,
                self.runtime_state,
                self.action_config.scroll,
                self.momentum
            ),

            # Zoom actions
            ActionName.ZOOM_IN: ZoomStepHandler(
                self.adapter,
                self.runtime_state,
                self.action_config.zoom,
                direction='in'
            ),
            ActionName.ZOOM_OUT: ZoomStepHandler(
                self.adapter,
                self.runtime_state,
                self.action_config.zoom,
                direction='out'
            ),
            ActionName.CONTINUOUS_ZOOM: ContinuousZoomHandler(
                self.adapter,
                self.runtime_state,
                self.action_config.zoom
            ),

            # Volume control
            ActionName.CONTINUOUS_VOLUME: ContinuousVolumeHandler(
                self.adapter,
                self.runtime_state,
                self.action_config.volume
            ),

            # Tab switching
            ActionName.CONTINUOUS_TAB: ContinuousTabHandler(
                self.adapter,
                self.runtime_state,
                self.action_config.tab
            ),

            # Desktop switching
            ActionName.SWITCH_DESKTOP: SwitchDesktopHandler(
                self.adapter,
                self.runtime_state
            ),

            # Keyboard actions
            ActionName.COPY: CopyHandler(
                self.adapter,
                self.runtime_state
            ),
            ActionName.PASTE: PasteHandler(
                self.adapter,
                self.runtime_state
            ),
            ActionName.UNDO: UndoHandler(
                self.adapter,
                self.runtime_state
            ),

            # Latch control
            ActionName.ENABLE_LATCH: EnableLatchHandler(
                self.adapter,
                self.runtime_state,
                self.state_machine
            ),
            ActionName.DISABLE_LATCH: DisableLatchHandler(
                self.adapter,
                self.runtime_state,
                self.state_machine
            ),

            # Habit awareness alerts
            ActionName.ALERT_FACIAL_CONTACT: CompositeAlertHandler(
                self.adapter,
                self.runtime_state,
                self.action_config.habit_alerts
            ),
        }

    def _process_gesture(self) -> None:
        """Process gesture events and handle state transitions."""
        try:
            # Get gesture event from queue (blocking with timeout)
            gesture_event: Optional[GestureEvent] = self.gesture_queue.get(timeout=0.01)

            if gesture_event is not None:
                self._handle_gesture_event(gesture_event)

        except Exception as e:
            if not self.runtime_state.shutdown_requested:
                log_debug(f"Gesture queue timeout or error: {e}")

        # Track gesture state transitions for continuous actions
        self._track_gesture_state()

    def _handle_gesture_event(self, gesture_event: GestureEvent) -> None:
        """Handle a gesture event from the queue."""
        # Map gesture to action
        action_name = self._map_gesture_to_action(gesture_event.gesture_name)

        if not action_name:
            log_debug(f"No action mapped for gesture: {gesture_event.gesture_name}")
            return

        # Update hand state from gesture metadata
        self.state_machine.update_hand_state(gesture_event.metadata)

        # Skip queue-based execution for click - handled by state transitions
        if action_name == ActionName.CLICK:
            return

        # Check if action should execute (debouncing, latch)
        if not self.state_machine.should_execute(gesture_event, action_name):
            return

        # Execute action via handler
        success = self._execute_action(action_name, gesture_event)

        if success:
            self._record_action_success(action_name, gesture_event)
        else:
            log_error("ACT-002", f"Action failed: {action_name}")

    def _track_gesture_state(self) -> None:
        """Track gesture state transitions for continuous actions."""
        # Get current gesture from RuntimeState
        with self.runtime_state.lock:
            current_gesture = self.runtime_state.latest_gesture

        # Detect state transition
        if current_gesture != self._last_tracked_gesture:
            # Check latch for state transitions
            if current_gesture is not None:
                action = self._map_gesture_to_action(current_gesture)
                if action and not self.state_machine.is_action_allowed(action):
                    log_debug(f"Gesture transition blocked by latch: {current_gesture} -> {action}")
                    return

            self._handle_gesture_transition(self._last_tracked_gesture, current_gesture)
            self._last_tracked_gesture = current_gesture
        elif current_gesture is not None:
            # Same gesture continuing - check latch
            action = self._map_gesture_to_action(current_gesture)
            if action and not self.state_machine.is_action_allowed(action):
                return

            self._handle_gesture_continue(current_gesture)

    def _handle_gesture_transition(self, old_gesture: Optional[str], new_gesture: Optional[str]) -> None:
        """Handle gesture start/end transitions."""
        # Create dummy event for handler callbacks
        dummy_event = GestureEvent(
            gesture_name=old_gesture or new_gesture or "",
            confidence=1.0,
            timestamp=time.time()
        )

        # Handle gesture END
        if old_gesture is not None:
            action = self._map_gesture_to_action(old_gesture)
            if action and action in self.handlers:
                self.handlers[action].on_gesture_end(dummy_event)

            # Flush gesture queue to prevent buffered events from executing after gesture ends
            # This prevents "lag" where volume/zoom/scroll continues after releasing the gesture
            flushed_count = 0
            while not self.gesture_queue.empty():
                try:
                    self.gesture_queue.get_nowait()
                    flushed_count += 1
                except Exception:
                    break

            if flushed_count > 0:
                log_debug(f"Flushed {flushed_count} queued gesture events after gesture end")

        # Handle gesture START
        if new_gesture is not None:
            action = self._map_gesture_to_action(new_gesture)
            if action and action in self.handlers:
                dummy_event.gesture_name = new_gesture
                self.handlers[action].on_gesture_start(dummy_event)
                # Mark gesture detected to trigger active FPS
                self.runtime_state.mark_gesture_detected()

    def _handle_gesture_continue(self, gesture_name: str) -> None:
        """Handle gesture continuation."""
        action = self._map_gesture_to_action(gesture_name)
        if action and action in self.handlers:
            dummy_event = GestureEvent(
                gesture_name=gesture_name,
                confidence=1.0,
                timestamp=time.time()
            )
            self.handlers[action].on_gesture_continue(dummy_event)
            # Keep active FPS while gesture continues
            self.runtime_state.mark_gesture_detected()

    def _map_gesture_to_action(self, gesture_name: str) -> Optional[ActionName]:
        """Map gesture name to action name via config."""
        action_str = self.action_config.mappings.get(gesture_name)
        if action_str is None:
            return None
        # Convert string to ActionName (handles both str and ActionName inputs)
        try:
            return ActionName(action_str) if isinstance(action_str, str) else action_str
        except ValueError:
            log_warning("ACT-003", f"Invalid action in config: {action_str}")
            return None

    def _execute_action(self, action_name: ActionName, gesture_event: GestureEvent) -> bool:
        """Execute action via handler."""
        if action_name not in self.handlers:
            log_warning("ACT-003", f"Unknown action: {action_name}")
            return False

        handler = self.handlers[action_name]
        return handler.execute(gesture_event)

    def _record_action_success(self, action_name: ActionName, gesture_event: GestureEvent) -> None:
        """Record successful action execution."""
        with self.runtime_state.lock:
            self.runtime_state.latest_action = action_name.value  # Store string value
            self.runtime_state.latest_action_time = time.time()
            self.runtime_state.actions_executed += 1
            self.runtime_state.mark_gesture_detected()

        log_info(
            f"Action executed: {action_name} "
            f"(from gesture: {gesture_event.gesture_name}, "
            f"confidence: {gesture_event.confidence:.2f})"
        )
