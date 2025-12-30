"""
Handsi controller for web UI.

Provides a clean API to start/stop/configure Handsi system
without blocking the main thread.
"""

import threading
from pathlib import Path
from typing import Optional

from handsi.actions.executor import ActionExecutorThread
from handsi.core.bus import RuntimeState, create_queues
from handsi.core.config import HandsiConfig, load_config, save_user_config, get_user_config_path
from handsi.core.logging import log_info, setup_logging
from handsi.gestures.infer import GestureInferenceThread
from handsi.vision.capture import CaptureThread
from handsi.vision.tracking import TrackingThread


class HandsiController:
    """
    Manages Handsi lifecycle for web UI.

    Handles starting/stopping threads and updating configuration
    without blocking the caller.
    """

    def __init__(self, config_path: str | Path):
        """
        Initialize controller with config.

        Args:
            config_path: Path to YAML config file
        """
        self.config_path = Path(config_path)
        self.config: Optional[HandsiConfig] = None
        self.runtime_state: Optional[RuntimeState] = None

        # Threads
        self.capture_thread: Optional[CaptureThread] = None
        self.tracking_thread: Optional[TrackingThread] = None
        self.gesture_thread: Optional[GestureInferenceThread] = None
        self.action_thread: Optional[ActionExecutorThread] = None

        # State
        self._running = False
        self._lock = threading.Lock()

        # Load initial config
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file."""
        self.config = load_config(self.config_path)
        log_info(f"Controller: Config loaded from {self.config_path}")

    def is_running(self) -> bool:
        """Check if Handsi is currently running."""
        with self._lock:
            return self._running

    def start(self) -> dict:
        """
        Start Handsi detection and control.

        Returns:
            dict: Status response with success/error
        """
        with self._lock:
            if self._running:
                return {"success": False, "error": "Already running"}

            try:
                # Create shared state and queues
                self.runtime_state = RuntimeState()
                frame_queue, feature_queue, gesture_queue = create_queues()

                # Create threads
                self.capture_thread = CaptureThread(
                    config=self.config.camera,
                    frame_queue=frame_queue,
                    runtime_state=self.runtime_state
                )

                self.tracking_thread = TrackingThread(
                    config=self.config.tracking,
                    frame_queue=frame_queue,
                    feature_queue=feature_queue,
                    runtime_state=self.runtime_state
                )

                self.gesture_thread = GestureInferenceThread(
                    config=self.config.gestures,
                    feature_queue=feature_queue,
                    gesture_queue=gesture_queue,
                    runtime_state=self.runtime_state
                )

                self.action_thread = ActionExecutorThread(
                    action_config=self.config.actions,
                    gesture_config=self.config.gestures,
                    macos_config=self.config.macos,
                    gesture_queue=gesture_queue,
                    runtime_state=self.runtime_state
                )

                # Start threads
                self.capture_thread.start()
                self.tracking_thread.start()
                self.gesture_thread.start()
                self.action_thread.start()

                self._running = True
                log_info("Controller: Handsi started successfully")

                return {"success": True, "message": "Handsi started"}

            except Exception as e:
                log_info(f"Controller: Failed to start - {e}")
                return {"success": False, "error": str(e)}

    def stop(self) -> dict:
        """
        Stop Handsi detection and control.

        Returns:
            dict: Status response with success/error
        """
        with self._lock:
            if not self._running:
                return {"success": False, "error": "Not running"}

            try:
                # Signal shutdown
                if self.runtime_state:
                    with self.runtime_state.lock:
                        self.runtime_state.shutdown_requested = True

                # Wait for threads to finish
                if self.capture_thread:
                    self.capture_thread.join(timeout=2.0)
                if self.tracking_thread:
                    self.tracking_thread.join(timeout=2.0)
                if self.gesture_thread:
                    self.gesture_thread.join(timeout=2.0)
                if self.action_thread:
                    self.action_thread.join(timeout=2.0)

                # Clean up
                self.capture_thread = None
                self.tracking_thread = None
                self.gesture_thread = None
                self.action_thread = None
                self.runtime_state = None

                self._running = False
                log_info("Controller: Handsi stopped successfully")

                return {"success": True, "message": "Handsi stopped"}

            except Exception as e:
                log_info(f"Controller: Failed to stop - {e}")
                return {"success": False, "error": str(e)}

    def get_status(self) -> dict:
        """
        Get current Handsi status.

        Returns:
            dict: Status information
        """
        with self._lock:
            if not self._running or not self.runtime_state:
                return {
                    "running": False,
                    "fps": 0,
                    "activity": "IDLE",
                    "frames_captured": 0,
                    "frames_processed": 0,
                    "latch_enabled": False
                }

            # Read from runtime state
            with self.runtime_state.lock:
                return {
                    "running": True,
                    "fps": self.runtime_state.current_fps,
                    "activity": self.runtime_state.activity_level.value,
                    "frames_captured": self.runtime_state.frames_captured,
                    "frames_processed": self.runtime_state.frames_processed,
                    "latch_enabled": self.runtime_state.latch_active
                }

    def get_settings(self) -> dict:
        """
        Get current configuration settings.

        Returns:
            dict: Current settings
        """
        return {
            "sensitivity": self.config.actions.mouse.sensitivity,
            "smoothing": self.config.actions.mouse.smoothing_factor,
            "dead_zone": self.config.actions.mouse.dead_zone,
            "pinch_threshold": self.config.gestures.pinch_threshold,
            "fist_threshold": self.config.gestures.fist_threshold,
            "swipe_velocity": self.config.gestures.swipe_velocity_threshold,
            "open_hand_spread": self.config.gestures.open_hand_spread_threshold,
            "thumbs_vertical": self.config.gestures.thumbs_vertical_threshold,
            "debounce_ms": self.config.gestures.debounce_ms,
            "latch_cooldown_ms": self.config.gestures.latch_cooldown_ms,
            "smoothing_window": self.config.gestures.smoothing_window,
            "mirror_x": self.config.actions.mouse.mirror_x
        }

    def update_settings(self, settings: dict) -> dict:
        """
        Update configuration settings.

        Note: Changes will take effect after restart.

        Args:
            settings: Dictionary of settings to update

        Returns:
            dict: Status response with success/error
        """
        try:
            # Update config object
            if "sensitivity" in settings:
                self.config.actions.mouse.sensitivity = float(settings["sensitivity"])
            if "smoothing" in settings:
                self.config.actions.mouse.smoothing_factor = float(settings["smoothing"])
            if "dead_zone" in settings:
                self.config.actions.mouse.dead_zone = float(settings["dead_zone"])
            if "pinch_threshold" in settings:
                self.config.gestures.pinch_threshold = float(settings["pinch_threshold"])
            if "fist_threshold" in settings:
                self.config.gestures.fist_threshold = float(settings["fist_threshold"])
            if "swipe_velocity" in settings:
                self.config.gestures.swipe_velocity_threshold = float(settings["swipe_velocity"])
            if "open_hand_spread" in settings:
                self.config.gestures.open_hand_spread_threshold = float(settings["open_hand_spread"])
            if "thumbs_vertical" in settings:
                self.config.gestures.thumbs_vertical_threshold = float(settings["thumbs_vertical"])
            if "debounce_ms" in settings:
                self.config.gestures.debounce_ms = int(settings["debounce_ms"])
            if "latch_cooldown_ms" in settings:
                self.config.gestures.latch_cooldown_ms = int(settings["latch_cooldown_ms"])
            if "smoothing_window" in settings:
                self.config.gestures.smoothing_window = int(settings["smoothing_window"])
            if "mirror_x" in settings:
                self.config.actions.mouse.mirror_x = bool(settings["mirror_x"])

            log_info(f"Controller: Settings updated in memory")

            # Save to user config file for persistence
            try:
                save_user_config(self.config)
                log_info(f"Controller: Settings saved to {get_user_config_path()}")
            except Exception as save_error:
                log_info(f"Controller: Warning - failed to save settings: {save_error}")
                # Continue anyway - settings are updated in memory

            # Note: Settings will take effect on next start
            # To apply immediately, would need to restart
            restart_needed = self.is_running()

            return {
                "success": True,
                "message": "Settings saved successfully",
                "restart_needed": restart_needed
            }

        except Exception as e:
            log_info(f"Controller: Failed to update settings - {e}")
            return {"success": False, "error": str(e)}

    def reset_to_defaults(self) -> dict:
        """
        Reset settings to defaults by deleting user config and reloading.

        Returns:
            dict: Status response with success/error
        """
        try:
            user_config_path = get_user_config_path()

            # Delete user config if it exists
            if user_config_path.exists():
                user_config_path.unlink()
                log_info(f"Controller: Deleted user config at {user_config_path}")
            else:
                log_info("Controller: No user config to delete")

            # Reload config from defaults
            self._load_config()
            log_info("Controller: Reloaded default config")

            # Note if restart is needed
            restart_needed = self.is_running()

            return {
                "success": True,
                "message": "Settings reset to defaults",
                "restart_needed": restart_needed
            }

        except Exception as e:
            log_info(f"Controller: Failed to reset to defaults - {e}")
            return {"success": False, "error": str(e)}
