"""
Scroll momentum (kinetic scrolling) for natural trackpad-like behavior.

Provides velocity-based scrolling that continues after gesture ends,
with configurable decay for smooth deceleration.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

from handsi.actions.adapters.base import ActionAdapter
from handsi.core.bus import RuntimeState
from handsi.core.config import ScrollConfig
from handsi.core.logging import log_debug, log_error, log_info


@dataclass
class MomentumConfig:
    """Configuration for scroll momentum."""
    enabled: bool = True
    decay: float = 0.95  # Velocity multiplier per frame (0-1)
    min_velocity: float = 5.0  # Minimum velocity to trigger momentum
    stop_threshold: float = 1.0  # Velocity below which momentum stops
    invert: bool = True  # Match scroll inversion setting


class ScrollMomentum:
    """
    Kinetic scrolling with velocity decay.

    Runs at 60Hz in a background thread, applying decaying scroll velocity
    after gesture ends with movement. Provides natural momentum like
    trackpad scrolling.
    """

    def __init__(
        self,
        adapter: ActionAdapter,
        config: MomentumConfig,
        runtime_state: RuntimeState
    ):
        """
        Initialize scroll momentum.

        Args:
            adapter: OS adapter for scroll execution
            config: Momentum configuration
            runtime_state: Shared runtime state for shutdown detection
        """
        self.adapter = adapter
        self.config = config
        self.runtime_state = runtime_state

        # Momentum state
        self._velocity: tuple[float, float] = (0.0, 0.0)
        self._active: bool = False
        self._lock = threading.Lock()

        # Velocity history for averaging
        self._velocity_history: deque[tuple[float, float]] = deque(maxlen=3)

        # Thread reference
        self._thread: Optional[threading.Thread] = None

    @classmethod
    def from_scroll_config(
        cls,
        adapter: ActionAdapter,
        scroll_config: ScrollConfig,
        runtime_state: RuntimeState
    ) -> "ScrollMomentum":
        """
        Create ScrollMomentum from ScrollConfig.

        Args:
            adapter: OS adapter
            scroll_config: Scroll configuration from app config
            runtime_state: Shared runtime state

        Returns:
            Configured ScrollMomentum instance
        """
        config = MomentumConfig(
            enabled=scroll_config.momentum_enabled,
            decay=scroll_config.momentum_decay,
            min_velocity=scroll_config.momentum_min_velocity,
            stop_threshold=scroll_config.momentum_stop_threshold,
            invert=scroll_config.invert
        )
        return cls(adapter, config, runtime_state)

    def start(self) -> threading.Thread:
        """
        Start momentum background thread.

        Returns:
            The started thread
        """
        self._thread = threading.Thread(
            target=self._momentum_loop,
            name="MomentumThread",
            daemon=True
        )
        self._thread.start()
        return self._thread

    def record_velocity(self, dx: float, dy: float) -> None:
        """
        Record scroll velocity for momentum calculation.

        Call this during active scrolling to build velocity history.

        Args:
            dx: Horizontal scroll velocity
            dy: Vertical scroll velocity
        """
        self._velocity_history.append((dx, dy))

    def trigger(self) -> None:
        """
        Start momentum based on recorded velocity history.

        Call this when scroll gesture ends to initiate kinetic scrolling.
        """
        if not self.config.enabled:
            return

        if len(self._velocity_history) == 0:
            return

        # Calculate average velocity from history
        avg_dx = sum(v[0] for v in self._velocity_history) / len(self._velocity_history)
        avg_dy = sum(v[1] for v in self._velocity_history) / len(self._velocity_history)
        magnitude = (avg_dx**2 + avg_dy**2) ** 0.5

        # Only trigger if velocity is significant
        if magnitude > self.config.min_velocity:
            with self._lock:
                self._velocity = (avg_dx, avg_dy)
                self._active = True
            log_debug(f"Scroll momentum started: dx={avg_dx:.1f}, dy={avg_dy:.1f}, magnitude={magnitude:.1f}")
        else:
            log_debug("No momentum: velocity below threshold")

        # Clear history for next gesture
        self._velocity_history.clear()

    def cancel(self) -> None:
        """
        Stop momentum immediately.

        Call this when user takes control (e.g., starts new scroll gesture).
        """
        with self._lock:
            self._active = False
            self._velocity = (0.0, 0.0)
        self._velocity_history.clear()

    def is_active(self) -> bool:
        """Check if momentum is currently active."""
        with self._lock:
            return self._active

    def _momentum_loop(self) -> None:
        """
        Background thread for scroll momentum.

        Runs at 60Hz, applying decaying scroll velocity.
        """
        log_info("Momentum thread started")
        sleep_time = 1.0 / 60.0  # 60 Hz

        try:
            while not self.runtime_state.shutdown_requested:
                # Check if momentum is enabled
                if not self.config.enabled:
                    time.sleep(sleep_time)
                    continue

                # Check if momentum is active
                with self._lock:
                    active = self._active
                    velocity = self._velocity

                if not active:
                    time.sleep(sleep_time)
                    continue

                # Apply momentum
                self._apply_momentum_frame(velocity)

                time.sleep(sleep_time)

        except Exception as e:
            log_error("MOM-001", f"Momentum loop error: {e}")
        finally:
            log_info("Momentum thread stopped")

    def _apply_momentum_frame(self, velocity: tuple[float, float]) -> None:
        """
        Apply one frame of momentum scrolling.

        Args:
            velocity: Current velocity (dx, dy)
        """
        velocity_dx, velocity_dy = velocity
        magnitude = (velocity_dx**2 + velocity_dy**2) ** 0.5

        if magnitude <= self.config.stop_threshold:
            # Velocity too low, stop momentum
            with self._lock:
                self._active = False
            log_debug("Momentum stopped (velocity below threshold)")
            return

        # Determine dominant direction (match active scrolling behavior)
        abs_vx = abs(velocity_dx)
        abs_vy = abs(velocity_dy)

        if abs_vy > abs_vx:
            # Vertical momentum dominant
            scroll_dx = 0
            scroll_dy = velocity_dy
        else:
            # Horizontal momentum dominant
            scroll_dx = velocity_dx
            scroll_dy = 0

        # Apply invert if enabled (consistent with active scrolling)
        if self.config.invert:
            scroll_dx = -scroll_dx
            scroll_dy = -scroll_dy

        # Execute scroll
        self.adapter.scroll(dx=int(scroll_dx), dy=int(scroll_dy))
        log_debug(f"Momentum scroll: dx={scroll_dx:.1f}, dy={scroll_dy:.1f}")

        # Decay velocity
        with self._lock:
            self._velocity = (
                velocity_dx * self.config.decay,
                velocity_dy * self.config.decay
            )

            # Check if we should stop
            new_magnitude = (self._velocity[0]**2 + self._velocity[1]**2) ** 0.5
            if new_magnitude < self.config.stop_threshold:
                self._active = False
                log_debug("Momentum stopped (velocity decayed below threshold)")
