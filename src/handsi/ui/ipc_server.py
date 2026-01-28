"""
IPC server for Tauri ↔ Python communication.

Reads JSON commands from stdin, executes them via HandsiController,
and writes JSON responses to stdout.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

from handsi.core.logging import log_info, setup_logging
from handsi.ui.controller import HandsiController


class IpcServer:
    """
    IPC server for stdio-based communication with Tauri.

    Protocol:
    - Commands: JSON objects on stdin, one per line
    - Responses: JSON objects on stdout, one per line

    Command format:
        {"command": "start", "args": {}}

    Response format:
        {"success": true, "data": {...}}
        {"success": false, "error": "error message"}
    """

    def __init__(self, config_path: str | Path):
        """
        Initialize IPC server.

        Args:
            config_path: Path to Handsi config file
        """
        self.controller = HandsiController(config_path)

        # Setup logging to file (not stdout, which is used for IPC)
        log_file = Path.home() / ".handsi" / "logs" / "handsi_ipc.log"
        setup_logging(
            log_level="INFO",
            log_file=str(log_file),
            debug=False
        )

        log_info("IPC server initialized")
        log_info(f"Config: {config_path}")

    def handle_command(self, command: str, args: Dict[str, Any], request_id: Any = None) -> Dict[str, Any]:
        """
        Handle a command from Tauri.

        Args:
            command: Command name
            args: Command arguments
            request_id: Optional request ID for correlation

        Returns:
            Response dictionary with 'success', 'data' or 'error', and 'request_id'
        """
        try:
            log_info(f"Handling command: {command} (request_id: {request_id})")

            if command == "start":
                result = self.controller.start()
            elif command == "stop":
                result = self.controller.stop()
            elif command == "get_status":
                result = self.controller.get_status()
            elif command == "get_settings":
                result = self.controller.get_settings()
            elif command == "update_settings":
                result = self.controller.update_settings(args)
            elif command == "get_info":
                result = self.controller.get_info()
            elif command == "get_mappings":
                result = self.controller.get_mappings()
            elif command == "update_mapping":
                gesture = args.get("gesture")
                enabled = args.get("enabled")
                result = self.controller.update_mapping(gesture, enabled)
            elif command == "update_mappings":
                mappings = args.get("mappings", {})
                result = self.controller.update_mappings(mappings)
            elif command == "get_available_gestures_and_actions":
                result = self.controller.get_available_gestures_and_actions()
            elif command == "get_habit_alert":
                result = self.controller.get_habit_alert()
            elif command == "get_cameras":
                result = self.controller.get_cameras()
            else:
                result = {
                    "success": False,
                    "error": f"Unknown command: {command}"
                }

            # Add request_id to response for correlation
            result["request_id"] = request_id
            return result

        except Exception as e:
            log_info(f"Error handling command {command}: {e}")
            return {
                "success": False,
                "error": str(e),
                "request_id": request_id
            }

    def run(self) -> None:
        """
        Run IPC server loop.

        Reads commands from stdin, processes them, and writes responses to stdout.
        Runs until stdin is closed or an error occurs.
        """
        log_info("Starting IPC server loop")

        try:
            # Read commands from stdin line by line
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Parse command
                    data = json.loads(line)
                    command = data.get("command")
                    args = data.get("args", {})
                    request_id = data.get("request_id")  # Extract request_id

                    # Handle command
                    response = self.handle_command(command, args, request_id)

                    # Write response to stdout
                    print(json.dumps(response), flush=True)

                except json.JSONDecodeError as e:
                    error_response = {
                        "success": False,
                        "error": f"Invalid JSON: {e}",
                        "request_id": None
                    }
                    print(json.dumps(error_response), flush=True)

                except Exception as e:
                    error_response = {
                        "success": False,
                        "error": f"Internal error: {e}",
                        "request_id": None
                    }
                    print(json.dumps(error_response), flush=True)

        except KeyboardInterrupt:
            log_info("IPC server interrupted")

        finally:
            # Cleanup: stop Handsi if running
            if self.controller.is_running():
                log_info("Stopping Handsi before exit")
                self.controller.stop()

            log_info("IPC server stopped")


def run_ipc_server(config_path: str | Path) -> None:
    """
    Run IPC server.

    Args:
        config_path: Path to Handsi config file
    """
    server = IpcServer(config_path)
    server.run()
