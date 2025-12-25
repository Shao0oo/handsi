"""
Utility functions for path resolution and common helpers.
"""

from pathlib import Path


def get_project_root() -> Path:
    """
    Get the project root directory (where pyproject.toml is located).

    Returns:
        Path to project root
    """
    # Go up from src/airdesk/core/utils.py to project root
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
