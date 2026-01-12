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
from handsi.core.registry import AVAILABLE_GESTURES, AVAILABLE_ACTIONS
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
        self._previous_device_id: Optional[int] = None  # Track device_id for restart detection

        # Load initial config
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file."""
        self.config = load_config(self.config_path)
        self._previous_device_id = self.config.camera.device_id  # Track initial device_id
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

                return {"success": True, "data": {"message": "Handsi started"}}

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

                return {"success": True, "data": {"message": "Handsi stopped"}}

            except Exception as e:
                log_info(f"Controller: Failed to stop - {e}")
                return {"success": False, "error": str(e)}

    def get_status(self) -> dict:
        """
        Get current Handsi status.

        Returns:
            dict: Status information wrapped in IPC response format
        """
        with self._lock:
            if not self._running or not self.runtime_state:
                return {
                    "success": True,
                    "data": {
                        "running": False,
                        "fps": 0,
                        "activity": "IDLE",
                        "frames_captured": 0,
                        "frames_processed": 0,
                        "latch_enabled": False
                    }
                }

            # Read from runtime state
            with self.runtime_state.lock:
                return {
                    "success": True,
                    "data": {
                        "running": True,
                        "fps": self.runtime_state.current_fps,
                        "activity": self.runtime_state.activity_level.value,
                        "frames_captured": self.runtime_state.frames_captured,
                        "frames_processed": self.runtime_state.frames_processed,
                        "latch_enabled": self.runtime_state.latch_active
                    }
                }

    def get_settings(self) -> dict:
        """
        Get current configuration settings.

        Returns:
            dict: Current settings wrapped in IPC response format
        """
        return {
            "success": True,
            "data": {
                "device_id": self.config.camera.device_id,
                "sensitivity": self.config.actions.mouse.sensitivity,
                "smoothing": self.config.actions.mouse.smoothing_factor,
                "dead_zone": self.config.actions.mouse.dead_zone,
                "scroll_sensitivity": self.config.actions.scroll.sensitivity,
                "scroll_dead_zone": self.config.actions.scroll.dead_zone,
                "pinch_threshold": self.config.gestures.pinch_threshold,
                "fist_threshold": self.config.gestures.fist_threshold,
                "swipe_velocity": self.config.gestures.swipe_velocity_threshold,
                "open_hand_spread": self.config.gestures.open_hand_spread_threshold,
                "thumbs_vertical": self.config.gestures.thumbs_vertical_threshold,
                "debounce_ms": self.config.gestures.debounce_ms,
                "latch_cooldown_ms": self.config.gestures.latch_cooldown_ms,
                "smoothing_window": self.config.gestures.smoothing_window,
                "mirror_x": self.config.actions.mouse.mirror_x,
                "invert_scroll": self.config.actions.scroll.invert
            }
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
            # Track which settings require restart
            gesture_settings_changed = False
            device_id_changed = False

            # Update config object
            if "sensitivity" in settings:
                self.config.actions.mouse.sensitivity = float(settings["sensitivity"])
            if "smoothing" in settings:
                self.config.actions.mouse.smoothing_factor = float(settings["smoothing"])
            if "dead_zone" in settings:
                self.config.actions.mouse.dead_zone = float(settings["dead_zone"])
            if "scroll_sensitivity" in settings:
                self.config.actions.scroll.sensitivity = float(settings["scroll_sensitivity"])
            if "scroll_dead_zone" in settings:
                self.config.actions.scroll.dead_zone = float(settings["scroll_dead_zone"])

            # Gesture settings - these require restart because GestureDetector stores them at init
            if "pinch_threshold" in settings:
                self.config.gestures.pinch_threshold = float(settings["pinch_threshold"])
                gesture_settings_changed = True
            if "fist_threshold" in settings:
                self.config.gestures.fist_threshold = float(settings["fist_threshold"])
                gesture_settings_changed = True
            if "swipe_velocity" in settings:
                self.config.gestures.swipe_velocity_threshold = float(settings["swipe_velocity"])
                gesture_settings_changed = True
            if "open_hand_spread" in settings:
                self.config.gestures.open_hand_spread_threshold = float(settings["open_hand_spread"])
                gesture_settings_changed = True
            if "thumbs_vertical" in settings:
                self.config.gestures.thumbs_vertical_threshold = float(settings["thumbs_vertical"])
                gesture_settings_changed = True
            if "debounce_ms" in settings:
                self.config.gestures.debounce_ms = int(settings["debounce_ms"])
                gesture_settings_changed = True
            if "latch_cooldown_ms" in settings:
                self.config.gestures.latch_cooldown_ms = int(settings["latch_cooldown_ms"])
                gesture_settings_changed = True
            if "smoothing_window" in settings:
                self.config.gestures.smoothing_window = int(settings["smoothing_window"])
                gesture_settings_changed = True

            if "mirror_x" in settings:
                self.config.actions.mouse.mirror_x = bool(settings["mirror_x"])
            if "invert_scroll" in settings:
                self.config.actions.scroll.invert = bool(settings["invert_scroll"])

            # Handle camera device_id - track changes for restart detection
            if "device_id" in settings:
                new_device_id = int(settings["device_id"])
                if new_device_id != self._previous_device_id:
                    device_id_changed = True
                    self._previous_device_id = new_device_id
                    log_info(f"Controller: Camera device changed from {self.config.camera.device_id} to {new_device_id}")
                self.config.camera.device_id = new_device_id

            log_info(f"Controller: Settings updated in memory")

            # Save to user config file for persistence
            try:
                save_user_config(self.config)
                log_info(f"Controller: Settings saved to {get_user_config_path()}")
            except Exception as save_error:
                log_info(f"Controller: Warning - failed to save settings: {save_error}")
                # Continue anyway - settings are updated in memory

            # Determine if restart is needed
            # - Camera device change requires restart to reopen camera
            # - Gesture settings changes require restart because GestureDetector copies values at init
            restart_needed = self.is_running() and (device_id_changed or gesture_settings_changed)

            # Determine restart reason for user feedback
            if device_id_changed and gesture_settings_changed:
                restart_reason = "camera_and_gesture_changes"
            elif device_id_changed:
                restart_reason = "camera_change"
            elif gesture_settings_changed:
                restart_reason = "gesture_settings_change"
            else:
                restart_reason = None

            return {
                "success": True,
                "data": {
                    "message": "Settings saved successfully",
                    "restart_needed": restart_needed,
                    "requires_restart_reason": restart_reason
                }
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
                "data": {
                    "message": "Settings reset to defaults",
                    "restart_needed": restart_needed
                }
            }

        except Exception as e:
            log_info(f"Controller: Failed to reset to defaults - {e}")
            return {"success": False, "error": str(e)}

    def restart(self) -> dict:
        """
        Restart Handsi by stopping and starting.

        Returns:
            dict: Status response with success/error
        """
        try:
            # Stop if running
            if self.is_running():
                stop_result = self.stop()
                if not stop_result["success"]:
                    return {
                        "success": False,
                        "error": f"Failed to stop during restart: {stop_result.get('error')}"
                    }

            # Start
            start_result = self.start()
            if not start_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to start during restart: {start_result.get('error')}"
                }

            log_info("Controller: Handsi restarted successfully")
            return {"success": True, "data": {"message": "Handsi restarted successfully"}}

        except Exception as e:
            log_info(f"Controller: Failed to restart - {e}")
            return {"success": False, "error": str(e)}

    def get_mappings(self) -> dict:
        """
        Get all gesture mappings, including unmapped gestures.

        Returns:
            dict: All gestures with their actions (or empty string if unmapped)
        """
        mappings = []
        for gesture in AVAILABLE_GESTURES:
            action = self.config.actions.mappings.get(gesture, None)
            mappings.append({
                "gesture": gesture,
                "action": action if action else "",  # Empty string if unmapped
                "enabled": action is not None
            })

        return {"success": True, "data": {"mappings": mappings}}

    def update_mapping(self, gesture: str, enabled: bool) -> dict:
        """
        Update a single gesture mapping (enable/disable).

        Args:
            gesture: Gesture name
            enabled: Whether to enable (True) or disable (False) this gesture

        Returns:
            dict: Status response with success/error
        """
        try:
            if enabled:
                # For now, we can't add new mappings without knowing the action
                # This would require the frontend to pass the action as well
                return {
                    "success": False,
                    "error": "Enabling gestures not yet supported. Use update_mappings instead."
                }
            else:
                # Disable by removing from mappings
                if gesture in self.config.actions.mappings:
                    del self.config.actions.mappings[gesture]
                    log_info(f"Controller: Mapping disabled for gesture: {gesture}")

                    # Save to user config
                    try:
                        save_user_config(self.config)
                        log_info(f"Controller: Mappings saved to {get_user_config_path()}")
                    except Exception as save_error:
                        log_info(f"Controller: Warning - failed to save mappings: {save_error}")

                    restart_needed = self.is_running()

                    return {
                        "success": True,
                        "data": {
                            "message": f"Mapping disabled for {gesture}",
                            "restart_needed": restart_needed
                        }
                    }
                else:
                    return {
                        "success": True,
                        "data": {
                            "message": f"Gesture {gesture} was already disabled"
                        }
                    }

        except Exception as e:
            log_info(f"Controller: Failed to update mapping - {e}")
            return {"success": False, "error": str(e)}

    def update_mappings(self, mappings: dict) -> dict:
        """
        Update gesture → action mappings.

        Args:
            mappings: Dictionary where keys are gestures and values are:
                     - action name (string) if enabled
                     - None/empty if disabled

        Returns:
            dict: Status response with success/error
        """
        try:
            # Update config - remove disabled mappings
            new_mappings = {}
            for gesture, action in mappings.items():
                if action and action.strip():  # Only include enabled mappings
                    new_mappings[gesture] = action

            self.config.actions.mappings = new_mappings
            log_info(f"Controller: Mappings updated - {len(new_mappings)} enabled")

            # Save to user config
            try:
                save_user_config(self.config)
                log_info(f"Controller: Mappings saved to {get_user_config_path()}")
            except Exception as save_error:
                log_info(f"Controller: Warning - failed to save mappings: {save_error}")

            restart_needed = self.is_running()

            return {
                "success": True,
                "data": {
                    "message": "Mappings updated successfully",
                    "restart_needed": restart_needed
                }
            }

        except Exception as e:
            log_info(f"Controller: Failed to update mappings - {e}")
            return {"success": False, "error": str(e)}

    def get_info(self) -> dict:
        """
        Alias for get_system_info() for IPC compatibility.

        Returns:
            dict: System information including version, camera, permissions
        """
        return self.get_system_info()

    def get_system_info(self) -> dict:
        """
        Get system information.

        Returns:
            dict: System information including version, camera, permissions
        """
        try:
            import platform
            import sys

            # Get camera info
            camera_info = {
                "device_id": self.config.camera.device_id,
                "resolution": list(self.config.camera.resolution),
                "fps_idle": self.config.camera.fps_idle,
                "fps_attentive": self.config.camera.fps_attentive,
                "fps_active": self.config.camera.fps_active
            }

            # Get system info
            system_info = {
                "platform": platform.system(),
                "version": platform.version(),
                "python_version": sys.version.split()[0]
            }

            # Check accessibility permissions (macOS only)
            permissions_status = "unknown"
            if platform.system() == "Darwin":
                try:
                    from handsi.actions.adapters.macos import MacOSAdapter
                    adapter = MacOSAdapter()
                    if adapter.initialize():
                        permissions_status = "granted"
                        adapter.cleanup()
                    else:
                        permissions_status = "denied"
                except Exception:
                    permissions_status = "unknown"

            return {
                "success": True,
                "data": {
                    "camera": camera_info,
                    "system": system_info,
                    "permissions_status": permissions_status
                }
            }

        except Exception as e:
            log_info(f"Controller: Failed to get system info - {e}")
            return {"success": False, "error": str(e)}

    def check_first_run(self) -> dict:
        """
        Check if this is the first run (user config doesn't exist).

        Returns:
            dict: Status with is_first_run boolean
        """
        user_config_path = get_user_config_path()
        is_first_run = not user_config_path.exists()

        return {
            "success": True,
            "data": {
                "is_first_run": is_first_run,
                "user_config_path": str(user_config_path)
            }
        }

    def get_available_gestures_and_actions(self) -> dict:
        """
        Get lists of all available gestures and actions.

        Returns:
            dict: Lists of gestures and actions from registry
        """
        return {
            "success": True,
            "data": {
                "gestures": AVAILABLE_GESTURES,
                "actions": AVAILABLE_ACTIONS
            }
        }
