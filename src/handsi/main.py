"""
Handsi main entrypoint.

Phase 1: Runs capture (Thread 1) and tracking (Thread 2) only.
Optionally displays preview window (Thread 5).
"""

import argparse
import os
import signal
import sys
import time
from pathlib import Path

# Disable matplotlib font cache rebuilding for faster startup
# This must be set BEFORE importing any libraries that use matplotlib
os.environ['MPLCONFIGDIR'] = str(Path.home() / '.handsi' / 'matplotlib')
# Skip font manager rebuild
os.environ['MPLBACKEND'] = 'Agg'  # Non-interactive backend (faster)

# Make this process a background-only app (no Dock icon)
# This prevents the Python backend from appearing in the Dock
if sys.platform == 'darwin':
    try:
        from Foundation import NSBundle
        from AppKit import NSApp, NSApplicationActivationPolicyProhibited
        # Set activation policy to prohibit Dock icon
        # This must be done early, before any GUI frameworks initialize
        info = NSBundle.mainBundle().infoDictionary()
        if info:
            info['LSUIElement'] = '1'
        if NSApp:
            NSApp.setActivationPolicy_(NSApplicationActivationPolicyProhibited)
    except ImportError:
        # PyObjC not available, skip (dev mode might not have it)
        pass
    except Exception:
        # Silently fail if setting activation policy doesn't work
        pass

from handsi.actions.executor import ActionExecutorThread
from handsi.core.bus import RuntimeState, create_queues
from handsi.core.config import load_config
from handsi.core.logging import log_info, setup_logging
from handsi.core.utils import find_config_path
from handsi.gestures.infer import GestureInferenceThread
# PreviewWindow imported conditionally (only for CLI mode with --preview)
from handsi.vision.capture import CaptureThread
from handsi.vision.tracking import TrackingThread


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Handsi - Contactless Desktop Control (Phase 1: Capture + Tracking)"
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/default.yaml",
        help="Path to config file (default: config/default.yaml)"
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show preview window with hand tracking overlay"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in CLI mode (background service) instead of launching GUI"
    )

    parser.add_argument(
        "--ipc",
        type=str,
        choices=["stdio"],
        help="Run in IPC mode for Tauri (stdio)"
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entrypoint for Handsi Phase 1.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Parse arguments
    args = parse_args()

    # Set OpenCV camera access workaround for macOS (only in CLI mode)
    # In GUI mode, we want the normal permission prompt to appear
    if sys.platform == "darwin" and args.cli:
        os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")

    # Find config file
    try:
        config_path = find_config_path(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    # IPC mode: Run as subprocess for Tauri
    if args.ipc:
        from handsi.ui.ipc_server import run_ipc_server
        try:
            run_ipc_server(config_path)
            return 0
        except Exception as e:
            print(f"IPC server error: {e}", file=sys.stderr)
            return 1

    # Default mode is now CLI (background service)
    # GUI mode: Use Tauri app (see scripts/dev-tauri.sh)
    if not args.cli:
        print("=" * 60)
        print("Handsi GUI Mode")
        print("=" * 60)
        print("Qt GUI has been replaced with Tauri.")
        print("")
        print("To run the GUI:")
        print("  ./scripts/dev-tauri.sh")
        print("")
        print("To run in CLI mode (background service):")
        print("  handsi --cli")
        print("")
        print("See docs/TAURI_MIGRATION.md for more info.")
        print("=" * 60)
        return 1

    # Load config
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"Failed to load config: {e}")
        return 1

    # Override config with CLI flags
    if args.preview:
        config.system.preview = True
    if args.debug:
        config.system.debug = True

    # Setup logging
    setup_logging(
        log_level=config.system.log_level,
        log_file=config.system.log_file,
        debug=config.system.debug
    )

    log_info("=" * 60)
    log_info("Handsi Phase 1 - Capture + Tracking + Gestures + Actions")
    log_info("=" * 60)
    log_info(f"Config: {args.config}")
    log_info(f"Preview: {config.system.preview}")
    log_info(f"Debug: {config.system.debug}")
    log_info("=" * 60)

    # Create shared state and queues
    runtime_state = RuntimeState()
    frame_queue, feature_queue, gesture_queue = create_queues()

    # Create threads
    capture_thread = CaptureThread(
        config=config.camera,
        frame_queue=frame_queue,
        runtime_state=runtime_state
    )

    tracking_thread = TrackingThread(
        config=config.tracking,
        frame_queue=frame_queue,
        feature_queue=feature_queue,
        runtime_state=runtime_state
    )

    gesture_thread = GestureInferenceThread(
        config=config.gestures,
        feature_queue=feature_queue,
        gesture_queue=gesture_queue,
        runtime_state=runtime_state
    )

    action_thread = ActionExecutorThread(
        action_config=config.actions,
        gesture_config=config.gestures,
        macos_config=config.macos,
        gesture_queue=gesture_queue,
        runtime_state=runtime_state
    )

    # Create preview window (non-threaded, runs in main loop)
    preview_window = None
    if config.system.preview:
        from handsi.ui.preview import PreviewWindow
        preview_window = PreviewWindow(
            runtime_state=runtime_state,
            tracking_thread=tracking_thread
        )
        if not preview_window.initialize():
            log_info("Preview disabled due to initialization error")
            preview_window = None

    # Setup signal handler for graceful shutdown
    def signal_handler(sig, frame):
        log_info("Shutdown signal received")
        with runtime_state.lock:
            runtime_state.shutdown_requested = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start threads
    log_info("Starting threads...")
    capture_thread.start()
    tracking_thread.start()
    gesture_thread.start()
    action_thread.start()

    log_info("All threads started. Press Ctrl+C to stop.")
    if preview_window:
        log_info("Preview: Press 'q' to quit, 'g' to toggle gestures, 'f' to toggle features")

    # Main loop
    try:
        while not runtime_state.shutdown_requested:
            # Update preview window if enabled
            if preview_window is not None:
                if not preview_window.update():
                    # User pressed 'q' in preview window
                    log_info("Preview window closed by user")
                    with runtime_state.lock:
                        runtime_state.shutdown_requested = True
                    break
            else:
                # No preview, just sleep
                time.sleep(0.1)

            # Periodically log stats in debug mode
            if config.system.debug:
                with runtime_state.lock:
                    log_info(
                        f"Stats: captured={runtime_state.frames_captured}, "
                        f"processed={runtime_state.frames_processed}, "
                        f"activity={runtime_state.activity_level.value}, "
                        f"fps={runtime_state.current_fps}"
                    )

    except KeyboardInterrupt:
        log_info("Keyboard interrupt received")

    # Shutdown
    log_info("Shutting down...")
    with runtime_state.lock:
        runtime_state.shutdown_requested = True

    # Clean up preview window
    if preview_window is not None:
        preview_window.cleanup()

    # Wait for threads to finish (with timeout)
    log_info("Waiting for threads to finish...")
    capture_thread.join(timeout=2.0)
    tracking_thread.join(timeout=2.0)
    gesture_thread.join(timeout=2.0)
    action_thread.join(timeout=2.0)

    log_info("Handsi stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
