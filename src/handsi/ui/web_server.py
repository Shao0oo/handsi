"""
Flask web server for Handsi control panel.

Provides REST API for starting/stopping Handsi and managing settings.
"""

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from handsi.core.logging import log_info, setup_logging
from handsi.ui.controller import HandsiController


def create_app(config_path: str | Path, debug: bool = False) -> Flask:
    """
    Create and configure Flask application.

    Args:
        config_path: Path to Handsi config file
        debug: Enable debug mode

    Returns:
        Configured Flask app
    """
    app = Flask(__name__, static_folder=None)
    CORS(app)  # Enable CORS for development

    # Initialize controller
    controller = HandsiController(config_path)

    # Store controller in app context
    app.controller = controller

    # Setup logging
    setup_logging(
        log_level="DEBUG" if debug else "INFO",
        log_file="logs/handsi_web.log",
        debug=debug
    )

    # Define static files directory
    web_dir = Path(__file__).parent / "web"

    # === Routes ===

    @app.route("/")
    def index():
        """Serve main HTML page."""
        return send_from_directory(web_dir, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        """Serve static files (CSS, JS)."""
        return send_from_directory(web_dir, filename)

    # === API Endpoints ===

    @app.route("/api/start", methods=["POST"])
    def start():
        """Start Handsi detection and control."""
        result = controller.start()
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @app.route("/api/stop", methods=["POST"])
    def stop():
        """Stop Handsi detection and control."""
        result = controller.stop()
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @app.route("/api/status", methods=["GET"])
    def status():
        """Get current Handsi status."""
        result = controller.get_status()
        return jsonify(result)

    @app.route("/api/settings", methods=["GET"])
    def get_settings():
        """Get current configuration settings."""
        result = controller.get_settings()
        return jsonify(result)

    @app.route("/api/settings", methods=["PUT"])
    def update_settings():
        """Update configuration settings."""
        settings = request.json
        result = controller.update_settings(settings)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @app.route("/api/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({"status": "ok"})

    # === Error Handlers ===

    @app.errorhandler(404)
    def not_found(e):
        """Handle 404 errors."""
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        """Handle 500 errors."""
        log_info(f"Server error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    return app


def run_server(
    config_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 5000,
    debug: bool = False
) -> None:
    """
    Run Flask web server.

    Args:
        config_path: Path to Handsi config file
        host: Host to bind to (default: 127.0.0.1)
        port: Port to bind to (default: 5000)
        debug: Enable debug mode
    """
    app = create_app(config_path, debug=debug)

    log_info("=" * 60)
    log_info("Handsi Web Control Panel")
    log_info("=" * 60)
    log_info(f"Server running at: http://{host}:{port}")
    log_info(f"Config: {config_path}")
    log_info(f"Debug: {debug}")
    log_info("=" * 60)
    log_info("Press Ctrl+C to stop")

    app.run(host=host, port=port, debug=debug, use_reloader=False)
