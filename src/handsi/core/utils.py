"""
Utility functions for path resolution and common helpers.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from handsi.core.config import HandsiConfig


def get_project_root() -> Path:
    """
    Get the project root directory (where pyproject.toml is located).

    When running from PyInstaller bundle, returns the Resources directory.
    When running normally, returns the project root.

    Returns:
        Path to project root or bundle resources
    """
    # Check if running from PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller extracts to _MEIPASS (Contents/Resources/)
        return Path(sys._MEIPASS)

    # Normal execution: go up from src/handsi/core/utils.py to project root
    return Path(__file__).parent.parent.parent.parent


def find_config_path(config_arg: str) -> Path:
    """
    Find config file, checking multiple locations.

    Priority:
    1. Absolute path provided by user
    2. Relative to current working directory
    3. Relative to project root (where pyproject.toml is)

    Args:
        config_arg: Config path from CLI argument

    Returns:
        Path to config file

    Raises:
        FileNotFoundError: If config not found in any location
    """
    config_path = Path(config_arg)

    # If absolute or exists relative to cwd, use it
    if config_path.is_absolute() or config_path.exists():
        return config_path

    # Try relative to project root
    project_root = get_project_root()
    project_config = project_root / config_arg
    if project_config.exists():
        return project_config

    # Not found anywhere
    raise FileNotFoundError(
        f"Config file not found: {config_arg}\n"
        f"Searched:\n"
        f"  - {config_path.absolute()}\n"
        f"  - {project_config}"
    )


def ensure_dir(path: Path) -> Path:
    """
    Ensure directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        Path object (for chaining)
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def needs_holistic_mode(config: HandsiConfig) -> bool:
    """
    Determine if holistic tracking mode is needed based on enabled features.

    Holistic mode (face + pose + hands) is required when any feature
    needs face or pose landmarks. Currently this includes:
    - habit_awareness.enabled + habit_awareness.facial_contact_enabled

    Args:
        config: Application configuration

    Returns:
        True if holistic mode is needed, False for hands-only mode
    """
    # Check habit awareness features
    if config.habit_awareness.enabled:
        if config.habit_awareness.facial_contact_enabled:
            return True
        # Future: Add other habit features that need face/pose here

    # Future: Add other features that need holistic data here
    # Example: if config.posture_awareness.enabled:
    #     return True

    return False
