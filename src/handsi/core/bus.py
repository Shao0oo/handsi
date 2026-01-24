"""
Core event bus and shared state for inter-thread communication.

Defines:
- RuntimeState: Shared state (activity level, FPS, gesture timing)
- Queue definitions for frame/feature/gesture data flow
- ActivityLevel enum
"""

import queue
import threading
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Optional

import numpy as np

from handsi.core.types import GestureMetadata


class ActivityLevel(Enum):
    """System activity level for adaptive FPS control."""
    IDLE = "idle"           # No hands detected for >3s → 1-2 Hz
    ATTENTIVE = "attentive" # Hands present, no gesture → 5 Hz
    ACTIVE = "active"       # Gesture detected/executing → 10 Hz


@dataclass
class RuntimeState:
    """
    Thread-safe shared state for the entire pipeline.

    All fields should be accessed/modified with the lock held.
    Use context manager: `with state.lock: ...`
    """
    lock: threading.RLock = field(default_factory=threading.RLock)

    # Activity tracking
    activity_level: ActivityLevel = ActivityLevel.IDLE
    current_fps: int = 2
    last_hands_detected_time: float = 0.0
    last_gesture_time: float = 0.0

    # System control
    system_active: bool = True      # Global enable/disable
    latch_active: bool = False      # Gesture control enabled (via latch gesture)
    shutdown_requested: bool = False

    # Statistics (for debug/preview)
    frames_captured: int = 0
    frames_processed: int = 0
    gestures_detected: int = 0

    # Latest gesture (for preview display)
    latest_gesture: Optional[str] = None
    latest_gesture_confidence: float = 0.0
    latest_gesture_time: float = 0.0

    # Latest action (for preview display)
    latest_action: Optional[str] = None
    latest_action_time: float = 0.0
    actions_executed: int = 0

    # Hand tracking state (for mouse movement normalization)
    hand_scale: float = 0.0  # Current hand size (wrist to MCP distance)
    cursor_position: tuple[float, float] = (0.0, 0.0)  # Normalized hand position

    # NEW: Habit alert state (for preview overlay)
    habit_alert_active: bool = False
    habit_alert_message: str = ""
    habit_alert_time: float = 0.0

    def update_activity_level(
        self,
        hands_detected: bool,
        idle_timeout: float = 3.0,
        attentive_timeout: float = 2.0, 
        fps: list = [2,10,20]
    ) -> None:
        """
        Update activity level based on hand detection and gesture timing.

        Args:
            hands_detected: Whether hands are currently detected
            idle_timeout: Seconds without hands before IDLE
            attentive_timeout: Seconds without gesture before ATTENTIVE
        """
        with self.lock:
            current_time = time()

            if hands_detected:
                self.last_hands_detected_time = current_time

            time_since_hands = current_time - self.last_hands_detected_time
            time_since_gesture = current_time - self.last_gesture_time

            # Determine new activity level
            if time_since_hands > idle_timeout:
                new_level = ActivityLevel.IDLE
                new_fps = fps[0]
            elif time_since_gesture < 1.0:
                # Active if gesture in last second
                new_level = ActivityLevel.ACTIVE
                new_fps = fps[2]
            else:
                # Hands present but no recent gesture
                new_level = ActivityLevel.ATTENTIVE
                new_fps = fps[1]

            # Update if changed
            if new_level != self.activity_level:
                self.activity_level = new_level
                self.current_fps = new_fps

    def mark_gesture_detected(self) -> None:
        """Mark that a gesture was just detected/executed."""
        with self.lock:
            self.last_gesture_time = time()
            self.gestures_detected += 1


@dataclass
class Frame:
    """Container for captured camera frame + metadata."""
    image: np.ndarray
    timestamp: float
    frame_number: int


@dataclass
class FeatureVector:
    """Container for extracted features + metadata."""
    features: dict[str, Any]  # Normalized landmark features
    timestamp: float
    frame_number: int
    hands_detected: bool
    hand_count: int
    face_detected: bool = False  # NEW: For holistic tracking
    pose_detected: bool = False  # NEW: For holistic tracking


@dataclass
class GestureEvent:
    """Container for detected gesture + metadata."""
    gesture_name: str
    confidence: float
    timestamp: float
    metadata: GestureMetadata = field(default_factory=dict)  # type: ignore[assignment]


# Queue type definitions
FrameQueue = queue.Queue[Optional[Frame]]
FeatureQueue = queue.Queue[Optional[FeatureVector]]
GestureQueue = queue.Queue[Optional[GestureEvent]]


def create_queues(
    frame_maxsize: int = 2,
    feature_maxsize: int = 5,
    gesture_maxsize: int = 10
) -> tuple[FrameQueue, FeatureQueue, GestureQueue]:
    """
    Create all pipeline queues with specified sizes.

    Args:
        frame_maxsize: Max frames in queue (small to prevent lag)
        feature_maxsize: Max feature vectors in queue
        gesture_maxsize: Max gesture events in queue

    Returns:
        Tuple of (frame_queue, feature_queue, gesture_queue)
    """
    return (
        queue.Queue(maxsize=frame_maxsize),
        queue.Queue(maxsize=feature_maxsize),
        queue.Queue(maxsize=gesture_maxsize)
    )
