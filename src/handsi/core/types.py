"""
Type definitions for the actions module.

Provides type-safe enums and TypedDicts for action names and gesture metadata,
enabling IDE autocomplete and compile-time validation.
"""

from enum import Enum
from typing import NotRequired, TypedDict


class ActionName(str, Enum):
    """
    All valid action names in the system.

    Inherits from str to allow seamless comparison with string values
    (e.g., from YAML config) while providing enum benefits.
    """

    # Mouse movement
    MOUSE_MOVE = "mouse_move"

    # Click actions
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"

    # Scroll actions
    SCROLL_UP = "scroll_up"
    SCROLL_DOWN = "scroll_down"
    CONTINUOUS_SCROLL = "continuous_scroll"

    # Zoom actions
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    CONTINUOUS_ZOOM = "continuous_zoom"

    # Volume control
    CONTINUOUS_VOLUME = "continuous_volume"

    # Desktop switching
    SWITCH_DESKTOP = "switch_desktop"

    # Latch control
    ENABLE_LATCH = "enable_latch"
    DISABLE_LATCH = "disable_latch"

    # Habit awareness alerts
    ALERT_FACIAL_CONTACT = "alert_facial_contact"
    ALERT_PHONE_SCROLLING = "alert_phone_scrolling"

    @classmethod
    def continuous_actions(cls) -> set["ActionName"]:
        """
        Get all continuous (non-discrete) actions.

        Continuous actions track state over time (scroll, zoom, volume)
        and don't use standard debouncing.
        """
        return {cls.MOUSE_MOVE, cls.CONTINUOUS_SCROLL, cls.CONTINUOUS_ZOOM, cls.CONTINUOUS_VOLUME}

    @classmethod
    def from_string(cls, value: str) -> "ActionName":
        """
        Convert string to ActionName, raising ValueError if invalid.

        Args:
            value: String action name (e.g., "click", "mouse_move")

        Returns:
            Corresponding ActionName enum value

        Raises:
            ValueError: If string is not a valid action name
        """
        try:
            return cls(value)
        except ValueError:
            valid_actions = [a.value for a in cls]
            raise ValueError(
                f"Invalid action name: '{value}'. "
                f"Valid actions: {valid_actions}"
            )


class GestureMetadata(TypedDict, total=False):
    """
    Expected metadata from gesture detection.

    TypedDict provides type hints for gesture metadata keys,
    enabling IDE autocomplete and type checking.

    All fields are optional (total=False) since different gestures
    may provide different metadata.
    """

    # Required fields (present in most gestures)
    hand_scale: float  # Distance from wrist to middle MCP (hand size reference)
    position: tuple[float, float]  # (x, y) hand center in normalized coords (0-1)
    hand_idx: int  # Which hand (0 or 1)
    handedness: str  # "Left" or "Right"

    # Optional fields (gesture-specific)
    distance: float  # Distance metric for pinch/open gestures
    extended_count: int  # Number of extended fingers
    direction: str  # Direction for swipe gestures ("left", "right", "up", "down")
    velocity: float  # Movement velocity for swipe detection

    # Habit awareness fields
    face_distance: NotRequired[float]  # Distance from hand to face (normalized by face scale)
    face_scale: NotRequired[float]  # Face scale reference (nose-to-chin distance)
    head_tilt: NotRequired[float]  # Head tilt angle (normalized by shoulder width)
    sustained_frames: NotRequired[int]  # Number of frames habit was sustained
    proportion: NotRequired[float]  # Proportion of frames with habit detected (0-1)
