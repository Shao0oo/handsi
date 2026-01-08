"""
Structured logging with error code prefixes.

Error code taxonomy:
- CAP-xxx: Capture errors
- TRK-xxx: Tracking errors
- FEA-xxx: Feature extraction errors
- GES-xxx: Gesture inference errors
- ACT-xxx: Action execution errors
- GUI-xxx: Preview window errors
- CFG-xxx: Configuration errors
"""

import logging
import sys
from pathlib import Path
from typing import Optional


class ErrorCodeFormatter(logging.Formatter):
    """Custom formatter that preserves error codes in messages."""

    def format(self, record: logging.LogRecord) -> str:
        # Format timestamp
        timestamp = self.formatTime(record, self.datefmt)

        # Format level with fixed width
        level = f"{record.levelname:5s}"

        # Format message (preserves error codes like TRK-001)
        message = record.getMessage()

        return f"[{timestamp}] [{level}] {message}"


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    debug: bool = False
) -> logging.Logger:
    """
    Configure structured logging for Handsi.

    Args:
        log_level: Logging level (DEBUG, INFO, WARN, ERROR)
        log_file: Optional file path for log output
        debug: If True, overrides log_level to DEBUG

    Returns:
        Configured logger instance
    """
    # Determine effective log level
    if debug:
        effective_level = logging.DEBUG
    else:
        effective_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger("handsi")
    logger.setLevel(effective_level)
    logger.handlers.clear()  # Clear any existing handlers

    # Create formatter
    formatter = ErrorCodeFormatter(
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler - use stderr to avoid interfering with IPC on stdout
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(effective_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(effective_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    """Get the configured Handsi logger."""
    return logging.getLogger("handsi")


# Error code helper functions
def log_error(code: str, message: str, **kwargs) -> None:
    """Log an error with error code prefix."""
    logger = get_logger()
    logger.error(f"{code}: {message}", **kwargs)


def log_warning(code: str, message: str, **kwargs) -> None:
    """Log a warning with error code prefix."""
    logger = get_logger()
    logger.warning(f"{code}: {message}", **kwargs)


def log_info(message: str, **kwargs) -> None:
    """Log an info message."""
    logger = get_logger()
    logger.info(message, **kwargs)


def log_debug(message: str, **kwargs) -> None:
    """Log a debug message."""
    logger = get_logger()
    logger.debug(message, **kwargs)
