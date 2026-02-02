"""
Configuration loading and validation using Pydantic.

Loads YAML config files and validates them against type-safe models.
"""

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel, Field, field_validator

from handsi.core.logging import log_error, log_info
from handsi.core.types import ActionName


class CameraConfig(BaseModel):
    """Camera capture settings."""
    device_id: int = Field(default=0, ge=0)
    device_name: str | None = Field(default=None)  # Camera name for validation
    resolution: tuple[int, int] = Field(default=(640, 480))
    fps_idle: int = Field(default=2, ge=1, le=30)
    fps_attentive: int = Field(default=5, ge=1, le=120)
    fps_active: int = Field(default=10, ge=1, le=360)

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
    model_complexity: int = Field(default=1, ge=0, le=1)  # 0=lite (faster), 1=full (more accurate)
    min_detection_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    min_tracking_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    idle_timeout: float = Field(default=3.0, ge=0.5, le=10.0)
    attentive_timeout: float = Field(default=2.0, ge=0.5, le=10.0)
    fps_idle: float = Field(default=2.0, ge=1.0, le=10.0)
    fps_attentive: float = Field(default=10.0, ge=1.0, le=60.0)
    fps_active: float = Field(default=20.0, ge=1.0, le=120.0)

    # Holistic tracking settings (always uses MediaPipe Holistic for hands + face + pose)
    holistic_model_complexity: int = Field(default=1, ge=0, le=2)
    holistic_min_detection_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    holistic_min_tracking_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class GestureConfig(BaseModel):
    """Gesture recognition settings."""
    debounce_ms: int = Field(default=300, ge=0, le=2000)
    latch_cooldown_ms: int = Field(default=500, ge=0, le=2000)
    latch_active: bool = Field(default=True)  # Start with gesture control enabled
    smoothing_window: int = Field(default=3, ge=1, le=10)
    consistency_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    # Detection thresholds (hand-relative: fraction of hand size)
    # Hand size = distance from wrist to middle finger MCP knuckle
    pinch_threshold: float = Field(default=0.2, ge=0.05, le=0.5)
    fist_threshold: float = Field(default=1.0, ge=0.3, le=2.0)
    open_hand_distance_threshold: float = Field(default=0.25, ge=0.1, le=0.6)  # DEPRECATED
    open_hand_spread_threshold: float = Field(default=0.3, ge=0.1, le=0.8)
    swipe_velocity_threshold: float = Field(default=0.8, ge=0.3, le=5.0)
    thumbs_vertical_threshold: float = Field(default=1.3, ge=0.5, le=2.0)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class MouseConfig(BaseModel):
    """Mouse movement settings."""
    mirror_x: bool = Field(default=True)
    smoothing_factor: float = Field(default=0.3, ge=0.0, le=1.0)
    dead_zone: float = Field(default=0.02, ge=0.0, le=0.03)
    dead_zone_curve: float = Field(default=2.0, ge=1.0, le=3.0)
    dead_zone_min_damping: float = Field(default=0.1, ge=0.0, le=0.5)
    sensitivity: float = Field(default=1.5, ge=0.1, le=10.0)
    interpolation_rate: float = Field(default=60.0, ge=10.0, le=120.0)


class ScrollConfig(BaseModel):
    """Scroll control settings."""
    sensitivity: float = Field(default=1.5, ge=0.1, le=10.0)
    dead_zone: float = Field(default=0.01, ge=0.0, le=0.03)
    dead_zone_curve: float = Field(default=2.0, ge=1.0, le=3.0)
    dead_zone_min_damping: float = Field(default=0.1, ge=0.0, le=0.5)
    max_scroll_per_frame: int = Field(default=100, ge=10, le=10000)
    invert: bool = Field(default=True)
    momentum_enabled: bool = Field(default=True)
    momentum_decay: float = Field(default=0.95, ge=0.0, le=0.99)
    momentum_min_velocity: float = Field(default=5.0, ge=0.1, le=10000.0)
    momentum_stop_threshold: float = Field(default=1.0, ge=0.1, le=10000.0)
    scroll_speed: int = Field(default=10, ge=1, le=100)  # pixels per discrete scroll event


class ZoomConfig(BaseModel):
    """Zoom control settings."""
    sensitivity: float = Field(default=3.0, ge=0.1, le=10.0)  # Higher = more frequent zoom steps
    dead_zone: float = Field(default=0.02, ge=0.0, le=0.05)
    dead_zone_curve: float = Field(default=2.0, ge=1.0, le=3.0)
    dead_zone_min_damping: float = Field(default=0.1, ge=0.0, le=0.5)
    zoom_step: float = Field(default=0.1, ge=0.01, le=1.0)  # zoom increment for discrete steps


class VolumeConfig(BaseModel):
    """Volume control settings."""
    mirror_x: bool = Field(default=True)  # Mirror X-coordinate for natural camera movement
    sensitivity: float = Field(default=3.0, ge=0.1, le=10.0)  # Higher = more frequent volume changes
    dead_zone: float = Field(default=0.02, ge=0.0, le=0.05)
    dead_zone_curve: float = Field(default=2.0, ge=1.0, le=3.0)
    dead_zone_min_damping: float = Field(default=0.1, ge=0.0, le=0.5)


class TabConfig(BaseModel):
    """Tab switching control settings."""
    sensitivity: float = Field(default=3.0, ge=0.1, le=10.0)  # Higher = more frequent tab switches
    dead_zone: float = Field(default=0.02, ge=0.0, le=0.05)
    dead_zone_curve: float = Field(default=2.0, ge=1.0, le=3.0)
    dead_zone_min_damping: float = Field(default=0.1, ge=0.0, le=0.5)


class AlertConfig(BaseModel):
    """Alert notification preferences for habit monitoring."""
    visual_enabled: bool = Field(default=True)
    audio_enabled: bool = Field(default=True)
    alert_cooldown_seconds: float = Field(default=3.0, ge=1.0, le=60.0)


class HabitAwarenessConfig(BaseModel):
    """Habit awareness settings (main toggle)."""
    enabled: bool = Field(default=False, description="Enable habit monitoring")

    # Facial contact settings
    facial_contact_enabled: bool = Field(default=True)
    facial_contact_distance_threshold: float = Field(default=0.3, ge=0.1, le=1.0)
    facial_contact_duration_threshold: float = Field(default=0.7, ge=0.5, le=1.0)


class ActionConfig(BaseModel):
    """Action execution settings."""
    mappings: dict[str, Union[str, ActionName]] = Field(default_factory=dict)
    mouse: MouseConfig = Field(default_factory=MouseConfig)
    scroll: ScrollConfig = Field(default_factory=ScrollConfig)
    zoom: ZoomConfig = Field(default_factory=ZoomConfig)
    volume: VolumeConfig = Field(default_factory=VolumeConfig)
    tab: TabConfig = Field(default_factory=TabConfig)
    habit_alerts: AlertConfig = Field(default_factory=AlertConfig)

    @field_validator("mappings")
    @classmethod
    def validate_mappings(cls, v: dict[str, Union[str, ActionName]]) -> dict[str, ActionName]:
        """Validate and convert action mappings to ActionName enum."""
        validated = {}
        for gesture, action in v.items():
            if isinstance(action, ActionName):
                validated[gesture] = action
            elif isinstance(action, str):
                try:
                    validated[gesture] = ActionName(action)
                except ValueError:
                    valid_actions = [a.value for a in ActionName]
                    raise ValueError(
                        f"Invalid action '{action}' for gesture '{gesture}'. "
                        f"Valid actions: {valid_actions}"
                    )
            else:
                raise ValueError(f"Action must be string or ActionName, got {type(action)}")
        return validated


def get_default_log_path() -> str:
    """Get default log file path in user's .handsi directory."""
    return str(Path.home() / ".handsi" / "logs" / "handsi.log")


class SystemConfig(BaseModel):
    """System-level settings."""
    log_level: str = Field(default="INFO")
    log_file: str = Field(default_factory=get_default_log_path)
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


class StillModeConfig(BaseModel):
    """Still Mode settings for presentation/focused use."""
    enabled: bool = Field(default=False)
    disabled_actions: list[Union[str, ActionName]] = Field(
        default_factory=lambda: [
            ActionName.MOUSE_MOVE,
            ActionName.CONTINUOUS_ZOOM,
            ActionName.DOUBLE_CLICK,
        ]
    )

    @field_validator("disabled_actions")
    @classmethod
    def validate_disabled_actions(cls, v: list[Union[str, ActionName]]) -> list[ActionName]:
        """Validate and convert disabled actions to ActionName enum."""
        validated = []
        for action in v:
            if isinstance(action, ActionName):
                validated.append(action)
            elif isinstance(action, str):
                try:
                    validated.append(ActionName(action))
                except ValueError:
                    valid_actions = [a.value for a in ActionName]
                    raise ValueError(
                        f"Invalid action '{action}' in disabled_actions. "
                        f"Valid actions: {valid_actions}"
                    )
            else:
                raise ValueError(f"Action must be string or ActionName, got {type(action)}")
        return validated


class StillModeConfig(BaseModel):
    """Still Mode settings for presentation/focused use."""
    enabled: bool = Field(default=False)
    disabled_actions: list[str] = Field(
        default_factory=lambda: ["mouse_move", "continuous_zoom", "double_click", "swipe"]
    )


class HandsiConfig(BaseModel):
    """Root configuration model."""
    camera: CameraConfig = Field(default_factory=CameraConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    gestures: GestureConfig = Field(default_factory=GestureConfig)
    actions: ActionConfig = Field(default_factory=ActionConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    macos: MacOSConfig = Field(default_factory=MacOSConfig)
    habit_awareness: HabitAwarenessConfig = Field(default_factory=HabitAwarenessConfig)


def clamp_nested_dict(data: dict, model_class) -> dict:
    """
    Recursively clamp values in a nested dictionary based on Pydantic model constraints.

    Args:
        data: Dictionary with potentially out-of-bounds values
        model_class: Pydantic model class with Field constraints

    Returns:
        Dictionary with clamped values
    """
    if not isinstance(data, dict):
        return data

    clamped = {}
    for key, value in data.items():
        if key not in model_class.model_fields:
            # Unknown field, keep as-is
            clamped[key] = value
            continue

        field_info = model_class.model_fields[key]

        # If field is a nested model, recurse
        if hasattr(field_info.annotation, 'model_fields'):
            if isinstance(value, dict):
                clamped[key] = clamp_nested_dict(value, field_info.annotation)
            else:
                clamped[key] = value
        # If field has numeric constraints, clamp
        elif isinstance(value, (int, float)):
            clamped_value = value

            # Get constraints from field metadata
            metadata = field_info.metadata if hasattr(field_info, 'metadata') else []
            for constraint in metadata:
                if hasattr(constraint, 'ge') and constraint.ge is not None:
                    if clamped_value < constraint.ge:
                        log_info(f"Config: Clamping {key}={clamped_value} to minimum {constraint.ge}")
                        clamped_value = constraint.ge
                if hasattr(constraint, 'le') and constraint.le is not None:
                    if clamped_value > constraint.le:
                        log_info(f"Config: Clamping {key}={clamped_value} to maximum {constraint.le}")
                        clamped_value = constraint.le

            clamped[key] = clamped_value
        else:
            # Other types, keep as-is
            clamped[key] = value

    return clamped


def load_config(config_path: str | Path) -> HandsiConfig:
    """
    Load and validate configuration from YAML file.

    Checks for user config first (~/.handsi/config.yaml), then falls back
    to the provided path (usually config/default.yaml).

    Args:
        config_path: Path to YAML config file (fallback if no user config)

    Returns:
        Validated HandsiConfig instance

    Raises:
        FileNotFoundError: If neither user config nor default config exists
        ValueError: If config is invalid
    """
    # Check for user config first
    user_config_path = get_user_config_path()
    if user_config_path.exists():
        config_to_load = user_config_path
        log_info(f"Loading user config from {user_config_path}")
    else:
        config_to_load = Path(config_path)
        log_info(f"No user config found, loading defaults from {config_path}")

    if not config_to_load.exists():
        log_error("CFG-001", f"Config file not found: {config_to_load}")
        raise FileNotFoundError(f"Config file not found: {config_to_load}")

    try:
        with open(config_to_load, "r") as f:
            raw_config = yaml.safe_load(f)

        if raw_config is None:
            raw_config = {}

        # First attempt: try loading directly
        try:
            config = HandsiConfig(**raw_config)
            log_info(f"Config loaded from {config_to_load}")
            return config
        except Exception as validation_error:
            # Validation failed - try clamping values
            log_info(f"Config validation failed, attempting to clamp out-of-bounds values: {validation_error}")

            # Clamp values based on model constraints
            clamped_config = clamp_nested_dict(raw_config, HandsiConfig)

            # Try loading again with clamped values
            config = HandsiConfig(**clamped_config)
            log_info(f"Config loaded with clamped values from {config_to_load}")

            # Save the clamped config back to file
            if config_to_load == user_config_path:
                try:
                    save_user_config(config)
                    log_info(f"Saved clamped config back to {user_config_path}")
                except Exception as save_error:
                    log_info(f"Warning: Could not save clamped config: {save_error}")

            return config

    except yaml.YAMLError as e:
        log_error("CFG-002", f"Invalid YAML syntax: {e}")
        raise ValueError(f"Invalid YAML syntax: {e}")

    except Exception as e:
        log_error("CFG-003", f"Config validation failed even after clamping: {e}")
        raise ValueError(f"Config validation failed: {e}")


def get_default_config() -> HandsiConfig:
    """Get default configuration (all defaults)."""
    return HandsiConfig()


def get_user_config_path() -> Path:
    """
    Get path to user configuration file.

    Returns:
        Path to ~/.handsi/config.yaml
    """
    # Use the same approach as IPC logs - just Path.home()!
    return Path.home() / ".handsi" / "config.yaml"


def save_user_config(config: HandsiConfig) -> None:
    """
    Save configuration to user config file.

    Creates ~/.handsi/ directory if it doesn't exist.

    Args:
        config: Configuration to save

    Raises:
        IOError: If unable to write config file
    """
    user_config_path = get_user_config_path()

    # Create directory if it doesn't exist
    user_config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Convert config to dict
        config_dict = config.model_dump()

        # Convert tuples to lists and enums to strings for YAML serialization
        # yaml.safe_load() cannot handle Python-specific tuple tags or enums
        def convert_for_yaml(obj):
            """Recursively convert tuples to lists and enums to strings for YAML compatibility."""
            if isinstance(obj, dict):
                return {k: convert_for_yaml(v) for k, v in obj.items()}
            elif isinstance(obj, tuple):
                return list(obj)
            elif isinstance(obj, list):
                return [convert_for_yaml(item) for item in obj]
            elif isinstance(obj, ActionName):
                return obj.value
            else:
                return obj

        config_dict = convert_for_yaml(config_dict)

        # Write to YAML
        with open(user_config_path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

        log_info(f"User config saved to {user_config_path}")

    except Exception as e:
        log_error("CFG-004", f"Failed to save user config: {e}")
        raise IOError(f"Failed to save user config: {e}")
