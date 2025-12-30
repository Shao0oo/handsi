"""
Qt application for Handsi control panel.

Creates a native window with embedded web view displaying HTML/CSS/JS interface.
"""

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

from handsi.core.logging import log_info, setup_logging
from handsi.ui.qt_bridge import HandsiBridge


class HandsiWindow(QMainWindow):
    """
    Main window for Handsi control panel.

    Embeds QWebEngineView displaying HTML/CSS/JS interface.
    """

    def __init__(self, config_path: str | Path, debug: bool = False):
        """
        Initialize window.

        Args:
            config_path: Path to Handsi config file
            debug: Enable debug mode
        """
        super().__init__()

        self.config_path = config_path
        self.debug = debug

        # Setup logging
        setup_logging(
            log_level="DEBUG" if debug else "INFO",
            log_file="logs/handsi_app.log",
            debug=debug
        )

        log_info("=" * 60)
        log_info("Handsi Native App - Qt WebEngine")
        log_info("=" * 60)
        log_info(f"Config: {config_path}")
        log_info(f"Debug: {debug}")
        log_info("=" * 60)

        # Create bridge for JavaScript ↔ Python communication
        self.bridge = HandsiBridge(config_path)

        # Setup UI
        self._setup_ui()
        self._setup_webchannel()
        self._load_html()

        log_info("Window initialized successfully")

    def _setup_ui(self) -> None:
        """Setup window UI."""
        self.setWindowTitle("Handsi Control Panel")
        self.resize(900, 800)

        # Center window on screen
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)

        # Create web view
        self.web_view = QWebEngineView()
        self.setCentralWidget(self.web_view)

        # Enable developer tools and JavaScript
        from PySide6.QtWebEngineCore import QWebEngineSettings
        settings = self.web_view.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )

        # Enable dev tools in debug mode (right-click -> Inspect)
        if self.debug:
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True
            )
            log_info("Developer tools enabled - Right-click page and select 'Inspect'")

    def _setup_webchannel(self) -> None:
        """Setup QWebChannel for JavaScript ↔ Python bridge."""
        # Create custom page with console logging
        from PySide6.QtWebEngineCore import QWebEnginePage

        class WebPage(QWebEnginePage):
            def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
                # Convert enum to string
                if level == QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel:
                    level_str = 'INFO'
                elif level == QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel:
                    level_str = 'WARNING'
                elif level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                    level_str = 'ERROR'
                else:
                    level_str = 'INFO'
                log_info(f"[JS {level_str}] {message} (line {lineNumber})")

        self.web_page = WebPage(self.web_view)
        self.web_view.setPage(self.web_page)

        # Setup channel
        self.channel = QWebChannel(self.web_page)
        self.channel.registerObject("bridge", self.bridge)
        self.web_page.setWebChannel(self.channel)

        log_info("QWebChannel configured")

    def _load_html(self) -> None:
        """Load HTML interface."""
        # Find HTML file
        web_dir = Path(__file__).parent / "web"
        html_file = web_dir / "index.html"

        if not html_file.exists():
            log_info(f"ERROR: HTML file not found: {html_file}")
            sys.exit(1)

        # Load HTML
        url = QUrl.fromLocalFile(str(html_file.absolute()))
        self.web_view.load(url)

        log_info(f"Loading HTML from: {html_file}")

    def closeEvent(self, event):
        """Handle window close event."""
        log_info("Window closing - stopping Handsi if running")

        # Stop Handsi if running
        if self.bridge.controller.is_running():
            self.bridge.stop()

        event.accept()


def run_app(
    config_path: str | Path,
    debug: bool = False
) -> int:
    """
    Run Qt application.

    Args:
        config_path: Path to Handsi config file
        debug: Enable debug mode

    Returns:
        Exit code
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Handsi")
    app.setOrganizationName("Handsi")

    window = HandsiWindow(config_path, debug=debug)
    window.show()

    return app.exec()
