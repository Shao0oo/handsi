"""
Configuration loading and validation using Pydantic.

Loads YAML config files and validates them against type-safe models.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from airdesk.core.logging import log_error, log_info


class CameraConfig(BaseModel):
    """Camera capture settings."""
    device_id: int = Field(default=0, ge=0)
    resolution: tuple[int, int] = Field(default=(640, 480))
    fps_idle: int = Field(default=2, ge=1, le=30)
    fps_attentive: int = Field(default=5, ge=1, le=30)
    fps_active: int = Field(default=10, ge=1, le=30)

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v: tuple[int, int]) -> tuple[int, int]:
        """Ensure resolution is positive."""
        if v[0] <= 0 or v[1] <= 0:
            raise ValueError("Resolution must be positive")
        return v


class TrackingConfig(BaseModel):
    """MediaPipe tracking settings."""
    max_hands: int = Field(default=2, ge=1, le=2)
    min_detection_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    min_tracking_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    idle_timeout: float = Field(default=3.0, ge=0.5, le=10.0)
    attentive_timeout: float = Field(default=2.0, ge=0.5, le=10.0)


class GestureConfig(BaseModel):
    """Gesture recognition settings."""
    debounce_ms: int = Field(default=300, ge=0, le=2000)
    latch_cooldown_ms: int = Field(default=500, ge=0, le=2000)
    smoothing_window: int = Field(default=3, ge=1, le=10)


class ActionConfig(BaseModel):
    """Action execution settings."""
    mappings: dict[str, str] = Field(default_factory=dict)


class SystemConfig(BaseModel):
    """System-level settings."""
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="logs/airdesk.log")
    preview: bool = Field(default=False)
    debug: bool = Field(default=False)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v_upper


class MacOSConfig(BaseModel):
    """macOS-specific settings."""
    accessibility_check: bool = Field(default=True)
    scroll_speed: int = Field(default=10, ge=1, le=100)
    zoom_step: float = Field(default=0.1, ge=0.01, le=1.0)


class AirDeskConfig(BaseModel):
    """Root configuration model."""
    camera: CameraConfig = Field(default_factory=CameraConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    gestures: GestureConfig = Field(default_factory=GestureConfig)
    actions: ActionConfig = Field(default_factory=ActionConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    macos: MacOSConfig = Field(default_factory=MacOSConfig)


def load_config(config_path: str | Path) -> AirDeskConfig:
    """
    Load and validate configuration from YAML file.

    Args:
        config_path: Path to YAML config file

    Returns:
        Validated AirDeskConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    config_path = Path(config_path)

    if not config_path.exists():
        log_error("CFG-001", f"Config file not found: {config_path}")
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with open(config_path, "r") as f:
            raw_config = yaml.safe_load(f)

        if raw_config is None:
            raw_config = {}

        config = AirDeskConfig(**raw_config)
        log_info(f"Config loaded from {config_path}")
        return config

    except yaml.YAMLError as e:
        log_error("CFG-002", f"Invalid YAML syntax: {e}")
        raise ValueError(f"Invalid YAML syntax: {e}")

    except Exception as e:
        log_error("CFG-003", f"Config validation failed: {e}")
        raise ValueError(f"Config validation failed: {e}")


def get_default_config() -> AirDeskConfig:
    """Get default configuration (all defaults)."""
    return AirDeskConfig()
