"""
Shared tracking logic for continuous hand-movement actions.

Extracts the common pattern used by scroll, zoom, and volume control:
- Anchor position management
- Delta calculation from anchor
- Hand scale normalization
- Dead zone application
- Accumulation with step thresholds
"""

from dataclasses import dataclass
from typing import Optional

from handsi.actions.adapters.base import apply_smooth_dead_zone


@dataclass
class ContinuousTrackerConfig:
    """Configuration for continuous action tracking."""
    dead_zone: float = 0.02
    dead_zone_curve: float = 2.0
    dead_zone_min_damping: float = 0.1
    sensitivity: float = 1.0
    step_threshold: float = 0.05  # Threshold for step-based actions (zoom, volume)


@dataclass
class DeltaResult:
    """Result of delta calculation."""
    dx: float  # Normalized, filtered delta X
    dy: float  # Normalized, filtered delta Y
    raw_dx: float  # Raw delta X (before filtering)
    raw_dy: float  # Raw delta Y (before filtering)


class ContinuousActionTracker:
    """
    Shared tracking logic for continuous hand-movement actions.

    Used by scroll, zoom, and volume handlers to eliminate code duplication.
    Handles:
    - Anchor position initialization and updates
    - Delta calculation from anchor
    - Hand scale normalization (distance-invariant movement)
    - Smooth dead zone application
    - Step accumulation for discrete actions
    """

    def __init__(self, config: ContinuousTrackerConfig):
        """
        Initialize the tracker.

        Args:
            config: Tracker configuration
        """
        self.config = config
        self._anchor_pos: Optional[tuple[float, float]] = None
        self._accumulated: float = 0.0

    @property
    def anchor_pos(self) -> Optional[tuple[float, float]]:
        """Get current anchor position."""
        return self._anchor_pos

    @property
    def accumulated(self) -> float:
        """Get accumulated movement value."""
        return self._accumulated

    def reset(self) -> None:
        """Reset anchor position and accumulator."""
        self._anchor_pos = None
        self._accumulated = 0.0

    def update(
        self,
        hand_pos: tuple[float, float],
        hand_scale: float
    ) -> Optional[DeltaResult]:
        """
        Calculate normalized, dead-zone-filtered delta from anchor.

        Args:
            hand_pos: Current hand position (normalized 0-1)
            hand_scale: Current hand scale for distance normalization

        Returns:
            DeltaResult with filtered deltas, or None if anchor just initialized
        """
        # Validate inputs
        if hand_scale <= 0.0:
            return None

        if not isinstance(hand_pos, tuple) or len(hand_pos) < 2:
            return None

        # Extract only (x, y) - ignore z if it exists
        hand_pos = (hand_pos[0], hand_pos[1])

        # Initialize anchor on first call
        if self._anchor_pos is None:
            self._anchor_pos = hand_pos
            return None

        # Calculate raw delta from anchor
        raw_dx = hand_pos[0] - self._anchor_pos[0]
        raw_dy = hand_pos[1] - self._anchor_pos[1]

        # Normalize by hand scale for distance-invariant movement
        # When hand is far (small scale), same screen delta = larger physical movement
        # When hand is close (large scale), same screen delta = smaller physical movement
        normalized_dx = raw_dx / hand_scale
        normalized_dy = raw_dy / hand_scale

        # Apply smooth dead zone
        filtered_dx, filtered_dy = apply_smooth_dead_zone(
            normalized_dx,
            normalized_dy,
            self.config.dead_zone,
            self.config.dead_zone_curve,
            self.config.dead_zone_min_damping
        )

        return DeltaResult(
            dx=filtered_dx,
            dy=filtered_dy,
            raw_dx=raw_dx,
            raw_dy=raw_dy
        )

    def update_anchor(self, hand_pos: tuple[float, float]) -> None:
        """
        Update anchor to current hand position.

        Call this after processing the delta to enable continuous tracking.

        Args:
            hand_pos: New anchor position
        """
        if isinstance(hand_pos, tuple) and len(hand_pos) >= 2:
            self._anchor_pos = (hand_pos[0], hand_pos[1])

    def accumulate(self, value: float) -> Optional[int]:
        """
        Accumulate movement and check if step threshold is crossed.

        Used for discrete actions like zoom steps or volume changes.

        Args:
            value: Value to accumulate (typically delta from update())

        Returns:
            Direction (-1 or 1) if threshold crossed, None otherwise
        """
        self._accumulated += value

        # Calculate effective threshold based on sensitivity
        effective_threshold = self.config.step_threshold / self.config.sensitivity

        if abs(self._accumulated) >= effective_threshold:
            direction = 1 if self._accumulated > 0 else -1
            self._accumulated = 0.0  # Reset accumulator
            return direction

        return None

    def accumulate_with_remainder(self, value: float) -> Optional[int]:
        """
        Accumulate movement and check threshold, keeping remainder.

        Unlike accumulate(), this preserves partial accumulation for
        smoother multi-step actions.

        Args:
            value: Value to accumulate

        Returns:
            Direction (-1 or 1) if threshold crossed, None otherwise
        """
        self._accumulated += value

        effective_threshold = self.config.step_threshold / self.config.sensitivity

        if abs(self._accumulated) >= effective_threshold:
            direction = 1 if self._accumulated > 0 else -1
            # Keep remainder for smooth multi-step behavior
            self._accumulated = self._accumulated % effective_threshold if direction > 0 else -(abs(self._accumulated) % effective_threshold)
            return direction

        return None
