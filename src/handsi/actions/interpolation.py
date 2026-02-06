"""
Cursor interpolation for smooth mouse movement at high frequency.

Provides 60Hz cursor updates independent of gesture detection rate (10Hz),
creating smooth, responsive cursor movement through exponential smoothing.
"""

import threading
import time
from dataclasses import dataclass
from typing import Optional

from handsi.actions.adapters.base import ActionAdapter, apply_smooth_dead_zone
from handsi.core.bus import RuntimeState
from handsi.core.config import MouseConfig
from handsi.core.logging import log_debug, log_error, log_info


@dataclass
class InterpolationConfig:
    """Configuration for cursor interpolation."""
    rate: float = 60.0  # Hz - interpolation update rate
    smoothing_factor: float = 0.3  # EMA smoothing (0=none, 1=max)
    sensitivity: float = 1.5  # Movement sensitivity multiplier
    mirror_x: bool = True  # Mirror X coordinate for natural camera movement
    dead_zone: float = 0.02  # Minimum movement threshold
    dead_zone_curve: float = 2.0  # Dead zone curve power
    dead_zone_min_damping: float = 0.1  # Minimum damping in dead zone
    staleness_timeout: float = 0.5  # Seconds before target is considered stale


class CursorInterpolator:
    """
    Smooth cursor interpolation at high frequency (60Hz).

    Runs independently of gesture detection rate, providing smooth cursor
    movement by interpolating between gesture updates using exponential
    moving average (EMA) smoothing.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        config: InterpolationConfig,
        runtime_state: RuntimeState
    ):
        """
        Initialize cursor interpolator.

        Args:
            adapter: OS adapter for mouse movement
            config: Interpolation configuration
            runtime_state: Shared runtime state
        """
        self.adapter = adapter
        self.config = config
        self.runtime_state = runtime_state

        # Interpolation state
        self._enabled: bool = False
        self._target_pos: Optional[tuple[float, float]] = None
        self._last_update_time: float = 0.0
        self._lock = threading.Lock()

        # Hand anchor for relative movement
        self._hand_anchor_pos: Optional[tuple[float, float]] = None

        # Thread reference
        self._thread: Optional[threading.Thread] = None

    @classmethod
    def from_mouse_config(
        cls,
        adapter: ActionAdapter,
        mouse_config: MouseConfig,
        runtime_state: RuntimeState
    ) -> "CursorInterpolator":
        """
        Create CursorInterpolator from MouseConfig.

        Args:
            adapter: OS adapter
            mouse_config: Mouse configuration from app config
            runtime_state: Shared runtime state

        Returns:
            Configured CursorInterpolator instance
        """
        config = InterpolationConfig(
            rate=mouse_config.interpolation_rate,
            smoothing_factor=mouse_config.smoothing_factor,
            sensitivity=mouse_config.sensitivity,
            mirror_x=mouse_config.mirror_x,
            dead_zone=mouse_config.dead_zone,
            dead_zone_curve=mouse_config.dead_zone_curve,
            dead_zone_min_damping=mouse_config.dead_zone_min_damping
        )
        return cls(adapter, config, runtime_state)

    def start(self) -> threading.Thread:
        """
        Start interpolation background thread.

        Returns:
            The started thread
        """
        self._thread = threading.Thread(
            target=self._interpolation_loop,
            name="InterpolationThread",
            daemon=True
        )
        self._thread.start()
        return self._thread

    def set_target(self, pos: tuple[float, float]) -> None:
        """
        Update target hand position for interpolation.

        Args:
            pos: Target hand position (normalized 0-1)
        """
        with self._lock:
            self._target_pos = pos
            self._last_update_time = time.time()
            # Ensure interpolation is enabled (may have been disabled due to staleness)
            self._enabled = True

    def enable(self) -> None:
        """Enable interpolation."""
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        """Disable interpolation."""
        with self._lock:
            self._enabled = False

    def reset_anchor(self) -> None:
        """Reset hand anchor position for new gesture."""
        self._hand_anchor_pos = None
        # Reset Rust's cursor tracking to actual OS position
        # This prevents teleporting after manual mouse movement
        self.adapter.reset_cursor_tracking()

    def is_enabled(self) -> bool:
        """Check if interpolation is enabled."""
        with self._lock:
            return self._enabled

    def _interpolation_loop(self) -> None:
        """
        Background thread for smooth cursor interpolation.

        Runs at configured rate (default 60Hz), providing smooth cursor
        movement independent of gesture detection rate.
        """
        log_info("Interpolation thread started")
        sleep_time = 1.0 / self.config.rate

        try:
            while not self.runtime_state.shutdown_requested:
                # Check if interpolation is enabled
                with self._lock:
                    enabled = self._enabled
                    target_pos = self._target_pos
                    last_update_time = self._last_update_time

                if not enabled or target_pos is None:
                    time.sleep(sleep_time)
                    continue

                # Check staleness
                current_time = time.time()
                staleness = current_time - last_update_time

                if staleness > self.config.staleness_timeout:
                    # Target is stale, disable interpolation
                    with self._lock:
                        self._enabled = False
                    log_debug("Interpolation disabled due to stale target")
                    time.sleep(sleep_time)
                    continue

                # Perform smooth cursor movement
                self._interpolate_to_target(target_pos)

                time.sleep(sleep_time)

        except Exception as e:
            log_error("INT-001", f"Interpolation loop error: {e}")
        finally:
            log_info("Interpolation thread stopped")

    def _interpolate_to_target(self, target_hand_pos: tuple[float, float]) -> None:
        """
        Move cursor smoothly toward target hand position.

        Uses exponential smoothing (EMA) for natural, responsive movement.

        Args:
            target_hand_pos: Target hand position (normalized 0-1)
        """
        # Get hand scale for distance normalization
        with self.runtime_state.lock:
            hand_scale = self.runtime_state.hand_scale

        if hand_scale <= 0.0:
            return

        # Apply X-coordinate mirroring if enabled
        if self.config.mirror_x:
            target_hand_pos = (1.0 - target_hand_pos[0], target_hand_pos[1])

        # Initialize anchor on first call
        if self._hand_anchor_pos is None:
            self._hand_anchor_pos = target_hand_pos
            log_debug(f"Interpolation anchor initialized to {target_hand_pos}")
            return

        # Calculate hand movement delta from anchor
        hand_dx = target_hand_pos[0] - self._hand_anchor_pos[0]
        hand_dy = target_hand_pos[1] - self._hand_anchor_pos[1]

        # Normalize by hand scale for distance-invariant movement
        hand_dx = hand_dx / hand_scale
        hand_dy = hand_dy / hand_scale

        # Apply smooth dead zone
        hand_dx, hand_dy = apply_smooth_dead_zone(
            hand_dx, hand_dy,
            self.config.dead_zone,
            self.config.dead_zone_curve,
            self.config.dead_zone_min_damping
        )

        if abs(hand_dx) < 0.0001 and abs(hand_dy) < 0.0001:
            return

        # Apply smoothing to delta
        # EMA simplifies to: smoothed_delta = alpha * delta * sensitivity
        alpha = 1.0 - self.config.smoothing_factor
        smoothed_dx = alpha * hand_dx * self.config.sensitivity
        smoothed_dy = alpha * hand_dy * self.config.sensitivity

        # Send delta to Rust - it queries actual OS position and applies delta
        # This avoids position caching issues when user manually moves the mouse
        self.adapter.move_mouse_relative(smoothed_dx, smoothed_dy)

        # Update anchor for continuous tracking
        self._hand_anchor_pos = target_hand_pos
