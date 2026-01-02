"""
Qt bridge for JavaScript ↔ Python communication.

Exposes HandsiController methods to JavaScript via QWebChannel.
"""

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from handsi.core.logging import log_info
from handsi.ui.controller import HandsiController


class HandsiBridge(QObject):
    """
    Qt bridge exposing Handsi controller to JavaScript.

    Signals are emitted for real-time UI updates (no polling needed).
    """

    # Signals for real-time updates
    statusChanged = Signal(str)  # Emits JSON string with status

    def __init__(self, config_path: str | Path):
        """
        Initialize bridge with HandsiController.

        Args:
            config_path: Path to YAML config file
        """
        super().__init__()
        self.controller = HandsiController(config_path)
        log_info("Qt Bridge initialized")

    @Slot(result=str)
    def start(self) -> str:
        """
        Start Handsi detection and control.

        Returns:
            JSON string with result
        """
        result = self.controller.start()
        log_info(f"Bridge: start() called - {result}")

        # Emit status change
        self._emit_status()

        return json.dumps(result)

    @Slot(result=str)
    def stop(self) -> str:
        """
        Stop Handsi detection and control.

        Returns:
            JSON string with result
        """
        result = self.controller.stop()
        log_info(f"Bridge: stop() called - {result}")

        # Emit status change
        self._emit_status()

        return json.dumps(result)

    @Slot(result=str)
    def getStatus(self) -> str:
        """
        Get current Handsi status.

        Returns:
            JSON string with status
        """
        result = self.controller.get_status()
        return json.dumps(result)

    @Slot(result=str)
    def getSettings(self) -> str:
        """
        Get current configuration settings.

        Returns:
            JSON string with settings
        """
        result = self.controller.get_settings()
        return json.dumps(result)

    @Slot(str, result=str)
    def updateSettings(self, settings_json: str) -> str:
        """
        Update configuration settings.

        Args:
            settings_json: JSON string with settings to update

        Returns:
            JSON string with result
        """
        try:
            settings = json.loads(settings_json)
            result = self.controller.update_settings(settings)
            log_info(f"Bridge: updateSettings() called - {result}")
            return json.dumps(result)
        except Exception as e:
            log_info(f"Bridge: updateSettings() failed - {e}")
            return json.dumps({"success": False, "error": str(e)})

    @Slot(result=str)
    def resetToDefaults(self) -> str:
        """
        Reset settings to defaults.

        Returns:
            JSON string with result
        """
        result = self.controller.reset_to_defaults()
        log_info(f"Bridge: resetToDefaults() called - {result}")
        return json.dumps(result)

    @Slot(result=str)
    def restart(self) -> str:
        """
        Restart Handsi (stop then start).

        Returns:
            JSON string with result
        """
        result = self.controller.restart()
        log_info(f"Bridge: restart() called - {result}")

        # Emit status change
        self._emit_status()

        return json.dumps(result)

    @Slot(result=str)
    def getMappings(self) -> str:
        """
        Get gesture → action mappings.

        Returns:
            JSON string with mappings
        """
        result = self.controller.get_mappings()
        return json.dumps(result)

    @Slot(str, result=str)
    def updateMappings(self, mappings_json: str) -> str:
        """
        Update gesture → action mappings.

        Args:
            mappings_json: JSON string with mappings to update

        Returns:
            JSON string with result
        """
        try:
            mappings = json.loads(mappings_json)
            result = self.controller.update_mappings(mappings)
            log_info(f"Bridge: updateMappings() called - {result}")
            return json.dumps(result)
        except Exception as e:
            log_info(f"Bridge: updateMappings() failed - {e}")
            return json.dumps({"success": False, "error": str(e)})

    @Slot(result=str)
    def getSystemInfo(self) -> str:
        """
        Get system information.

        Returns:
            JSON string with system info
        """
        result = self.controller.get_system_info()
        return json.dumps(result)

    @Slot(result=str)
    def checkFirstRun(self) -> str:
        """
        Check if this is the first run.

        Returns:
            JSON string with first run status
        """
        result = self.controller.check_first_run()
        return json.dumps(result)

    @Slot(result=str)
    def getAvailableGesturesAndActions(self) -> str:
        """
        Get available gestures and actions.

        Returns:
            JSON string with gestures and actions lists
        """
        result = self.controller.get_available_gestures_and_actions()
        return json.dumps(result)

    def _emit_status(self) -> None:
        """Emit status change signal."""
        status = self.controller.get_status()
        self.statusChanged.emit(json.dumps(status))

    def start_status_updates(self) -> None:
        """
        Start periodic status updates (optional).

        Note: Not needed if frontend polls getStatus(),
        but can be used for push-based updates.
        """
        # Could implement QTimer here for periodic updates
        # For now, we'll let frontend poll
        pass
