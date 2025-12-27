"""
Configuration loading and validation using Pydantic.

Loads YAML config files and validates them against type-safe models.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from handsi.core.logging import log_error, log_info


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
    consistency_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    # Detection thresholds (hand-relative: fraction of hand size)
    # Hand size = distance from wrist to middle finger MCP knuckle
    pinch_threshold: float = Field(default=0.2, ge=0.05, le=0.5)
    fist_threshold: float = Field(default=0.65, ge=0.3, le=1.0)
    open_hand_distance_threshold: float = Field(default=0.25, ge=0.1, le=0.6)  # DEPRECATED
    open_hand_spread_threshold: float = Field(default=0.3, ge=0.1, le=0.8)
    swipe_velocity_threshold: float = Field(default=0.8, ge=0.3, le=5.0)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class MouseConfig(BaseModel):
    """Mouse movement settings."""
    mirror_x: bool = Field(default=True)
    smoothing_factor: float = Field(default=0.3, ge=0.0, le=1.0)
    dead_zone: float = Field(default=0.02, ge=0.0, le=0.1)
    sensitivity: float = Field(default=1.5, ge=0.1, le=5.0)
    interpolation_rate: float = Field(default=60.0, ge=10.0, le=120.0)


class ActionConfig(BaseModel):
    """Action execution settings."""
    mappings: dict[str, str] = Field(default_factory=dict)
    mouse: MouseConfig = Field(default_factory=MouseConfig)


class SystemConfig(BaseModel):
    """System-level settings."""
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="logs/handsi.log")
    preview: bool = Field(default=False)
    preview_show_features: bool = Field(default=False)
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


class HandsiConfig(BaseModel):
    """Root configuration model."""
    camera: CameraConfig = Field(default_factory=CameraConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    gestures: GestureConfig = Field(default_factory=GestureConfig)
    actions: ActionConfig = Field(default_factory=ActionConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    macos: MacOSConfig = Field(default_factory=MacOSConfig)


def load_config(config_path: str | Path) -> HandsiConfig:
    """
    Load and validate configuration from YAML file.

    Args:
        config_path: Path to YAML config file

    Returns:
        Validated HandsiConfig instance

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

        config = HandsiConfig(**raw_config)
        log_info(f"Config loaded from {config_path}")
        return config

    except yaml.YAMLError as e:
        log_error("CFG-002", f"Invalid YAML syntax: {e}")
        raise ValueError(f"Invalid YAML syntax: {e}")

    except Exception as e:
        log_error("CFG-003", f"Config validation failed: {e}")
        raise ValueError(f"Config validation failed: {e}")


def get_default_config() -> HandsiConfig:
    """Get default configuration (all defaults)."""
    return HandsiConfig()
