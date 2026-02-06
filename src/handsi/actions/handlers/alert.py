"""
Alert handlers for habit awareness notifications.

Provides multi-modal alerts (visual overlay, audio beep)
for detected negative habits like facial contact (i.e. picking at pimples, pulling at hairs, etc).
Can easily be extended to detect other habits.

"""

import subprocess
import sys
import time
from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.actions.handlers.base import ContinuousActionHandler
from handsi.core.bus import GestureEvent, RuntimeState
from handsi.core.config import AlertConfig
from handsi.core.logging import log_info, log_warning


class BaseAlertHandler(ContinuousActionHandler):
    """
    Base class for alert actions with cooldown logic.

    Alerts use ContinuousActionHandler pattern because:
    - Visual alerts should be active while gesture is detected
    - Alerts should clear when gesture ends
    - Lifecycle hooks (on_gesture_start/continue/end) manage state

    Cooldown prevents audio spam - the same alert won't fire again
    until the cooldown expires.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        alert_config: AlertConfig
    ):
        super().__init__(adapter, runtime_state)
        self.alert_config = alert_config
        self.last_alert_time = 0.0
        self.alert_cooldown = alert_config.alert_cooldown_seconds

    def should_alert(self) -> bool:
        """Check if enough time passed since last alert (for audio cooldown)."""
        current_time = time.time()
        if current_time - self.last_alert_time > self.alert_cooldown:
            self.last_alert_time = current_time
            return True
        return False

    def reset_tracking(self) -> None:
        """Reset alert state. Override in subclasses."""
        pass


class VisualAlertHandler(BaseAlertHandler):
    """
    Display visual alert in Tauri GUI.

    Sets RuntimeState flags that the frontend polls to show/hide alert banner.
    Uses ContinuousActionHandler lifecycle:
    - on_gesture_start: Show alert
    - on_gesture_continue: Keep alert active
    - on_gesture_end: Clear alert
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        alert_config: AlertConfig
    ):
        super().__init__(adapter, runtime_state, alert_config)
        self._is_active = False

    def reset_tracking(self) -> None:
        """Clear visual alert state."""
        if self._is_active:
            self._is_active = False
            with self.runtime_state.lock:
                self.runtime_state.habit_alert_active = False
            log_info("Visual alert cleared")

    def on_gesture_start(self, event: GestureEvent) -> None:
        """Show alert when gesture starts."""
        self._is_active = True
        message = self._get_message(event)
        with self.runtime_state.lock:
            self.runtime_state.habit_alert_active = True
            self.runtime_state.habit_alert_message = message
            self.runtime_state.habit_alert_time = time.time()
        log_info(f"Visual alert active: {message}")

    def on_gesture_continue(self, event: GestureEvent) -> None:
        """Keep alert active while gesture continues."""
        # Ensure alert stays active (handles any missed start events)
        if not self._is_active:
            self.on_gesture_start(event)

    def on_gesture_end(self, event: GestureEvent) -> None:
        """Clear alert when gesture ends."""
        self.reset_tracking()

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute is handled by lifecycle hooks - this is a no-op."""
        return True

    def _get_message(self, event: GestureEvent) -> str:
        """Get alert message for gesture."""
        messages = {
            "facial_contact": "Habit Alert: Hand to Face",
            "phone_scrolling": "Habit Alert: Check Your Posture"
        }
        return messages.get(event.gesture_name, "Habit Detected")


class AudioAlertHandler(BaseAlertHandler):
    """
    Play audio alert sound.

    Audio is a one-shot action with cooldown - plays once when gesture
    starts, won't repeat until cooldown expires.
    """

    def on_gesture_start(self, event: GestureEvent) -> None:
        """Play sound once when gesture starts (with cooldown)."""
        if not self.should_alert():
            return

        try:
            if sys.platform == 'darwin':
                # macOS beep
                subprocess.Popen(
                    ['afplay', '/System/Library/Sounds/Ping.aiff'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            # elif sys.platform == 'linux':
            #     # Linux beep
            #     subprocess.Popen(
            #         ['paplay', '/usr/share/sounds/freedesktop/stereo/bell.oga'],
            #         check=False,
            #         timeout=1
            #     )
            log_info(f"Audio alert triggered for: {event.gesture_name}")

        except Exception as e:
            log_warning("ALT-001", f"Audio alert failed: {e}")

    def on_gesture_continue(self, event: GestureEvent) -> None:
        """Audio is one-shot, don't repeat on continue."""
        pass

    def on_gesture_end(self, event: GestureEvent) -> None:
        """Nothing to clean up for audio."""
        pass

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute is handled by lifecycle hooks - this is a no-op."""
        return True


class CompositeAlertHandler(ContinuousActionHandler):
    """
    Execute multiple alert types based on config.

    Combines visual and audio alerts into a single handler
    that respects individual enable/disable settings.

    Uses ContinuousActionHandler to properly manage lifecycle:
    - on_gesture_start: Activate all alerts
    - on_gesture_continue: Keep alerts active
    - on_gesture_end: Clear all alerts
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        runtime_state: RuntimeState,
        alert_config: AlertConfig
    ):
        super().__init__(adapter, runtime_state)
        self.alert_config = alert_config

        # Create enabled alert handlers
        self.handlers: list[BaseAlertHandler] = []

        if alert_config.visual_enabled:
            self.handlers.append(
                VisualAlertHandler(adapter, runtime_state, alert_config)
            )

        if alert_config.audio_enabled:
            self.handlers.append(
                AudioAlertHandler(adapter, runtime_state, alert_config)
            )

        log_info(
            f"CompositeAlertHandler initialized with {len(self.handlers)} handlers "
            f"(visual={alert_config.visual_enabled}, audio={alert_config.audio_enabled})"
        )

    def reset_tracking(self) -> None:
        """Delegate reset to all handlers."""
        for handler in self.handlers:
            handler.reset_tracking()

    def on_gesture_start(self, event: GestureEvent) -> None:
        """Delegate gesture start to all handlers."""
        for handler in self.handlers:
            handler.on_gesture_start(event)

    def on_gesture_continue(self, event: GestureEvent) -> None:
        """Delegate gesture continue to all handlers."""
        for handler in self.handlers:
            handler.on_gesture_continue(event)

    def on_gesture_end(self, event: GestureEvent) -> None:
        """Delegate gesture end to all handlers."""
        for handler in self.handlers:
            handler.on_gesture_end(event)

    def execute(self, event: Optional[GestureEvent] = None) -> bool:
        """Execute is handled by lifecycle hooks - this is a no-op."""
        return True

    def cleanup(self) -> None:
        """Clean up all handlers."""
        for handler in self.handlers:
            handler.cleanup()
