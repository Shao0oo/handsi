"""
Camera enumeration utilities.

Detects available cameras and their names without adding new dependencies.
Uses platform-specific tools for names and OpenCV for availability checking.

Platform support:
- macOS: Uses system_profiler for camera names
- Windows: Fallback to OpenCV indices (names not yet implemented)
- Linux: Fallback to OpenCV indices (names not yet implemented)
"""

import json
import platform
import subprocess
from dataclasses import dataclass
from typing import Optional

import cv2

from handsi.core.logging import log_info, log_warning


@dataclass
class CameraInfo:
    """Information about a detected camera."""
    index: int
    name: str
    available: bool


def _get_system_profiler_cameras() -> list[str]:
    """
    Get camera names from macOS system_profiler.

    Returns:
        List of camera names in order reported by macOS.
    """
    try:
        result = subprocess.run(
            ["system_profiler", "SPCameraDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            log_warning("CAM-001", f"system_profiler returned non-zero: {result.returncode}")
            return []

        data = json.loads(result.stdout)
        cameras = data.get("SPCameraDataType", [])

        # Extract camera names
        names = []
        for cam in cameras:
            name = cam.get("_name", "Unknown Camera")
            names.append(name)

        return names
    except subprocess.TimeoutExpired:
        log_warning("CAM-001", "system_profiler timed out after 10 seconds")
        return []
    except json.JSONDecodeError as e:
        log_warning("CAM-001", f"Failed to parse system_profiler JSON: {e}")
        return []
    except Exception as e:
        log_warning("CAM-001", f"Failed to get camera names from system_profiler: {e}")
        return []


def _probe_opencv_cameras(max_index: int = 10) -> list[int]:
    """
    Probe which camera indices are available via OpenCV.

    Args:
        max_index: Maximum index to probe (default 10)

    Returns:
        List of available camera indices
    """
    available = []
    consecutive_failures = 0
    max_consecutive_failures = 3  # Stop probing after 3 consecutive failures

    for i in range(max_index):
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                consecutive_failures = 0  # Reset on success
                # Quick validation - try to read a frame
                ret, _ = cap.read()
                cap.release()
                if ret:
                    available.append(i)
                else:
                    # Camera opens but doesn't provide frames
                    # Still include it but it may be problematic
                    available.append(i)
            else:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    # Stop probing - likely no more cameras
                    break
        except Exception as e:
            log_warning("CAM-003", f"Error probing camera index {i}: {e}")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                break

    return available


def _enumerate_macos() -> list[CameraInfo]:
    """
    Enumerate cameras on macOS.

    Combines system_profiler names with OpenCV index probing.

    Returns:
        List of CameraInfo objects
    """
    # Get names from system_profiler
    sp_names = _get_system_profiler_cameras()
    log_info(f"system_profiler found {len(sp_names)} cameras: {sp_names}")

    # Probe OpenCV indices
    available_indices = _probe_opencv_cameras()
    log_info(f"OpenCV found cameras at indices: {available_indices}")

    cameras = []

    # Match names to indices
    # Assumption: system_profiler order often matches OpenCV index order
    for i, idx in enumerate(available_indices):
        if i < len(sp_names):
            name = sp_names[i]
        else:
            name = f"Camera {idx}"

        cameras.append(CameraInfo(
            index=idx,
            name=name,
            available=True
        ))

    # If no cameras found via OpenCV, report system_profiler cameras as unavailable
    if not cameras and sp_names:
        for i, name in enumerate(sp_names):
            cameras.append(CameraInfo(
                index=i,
                name=f"{name} (not accessible)",
                available=False
            ))

    return cameras


def _enumerate_windows() -> list[CameraInfo]:
    """
    Enumerate cameras on Windows.

    Currently uses fallback (OpenCV indices only).
    Future: implement wmic or DirectShow enumeration.

    Returns:
        List of CameraInfo objects
    """
    log_info("Windows camera enumeration not yet implemented, using indices only")
    return _enumerate_fallback()


def _enumerate_linux() -> list[CameraInfo]:
    """
    Enumerate cameras on Linux.

    Currently uses fallback (OpenCV indices only).
    Future: implement v4l2-ctl enumeration.

    Returns:
        List of CameraInfo objects
    """
    log_info("Linux camera enumeration not yet implemented, using indices only")
    return _enumerate_fallback()


def _enumerate_fallback() -> list[CameraInfo]:
    """
    Fallback camera enumeration using OpenCV only.

    No camera names, just indices.

    Returns:
        List of CameraInfo objects with generic names
    """
    cameras = []
    available_indices = _probe_opencv_cameras()

    for idx in available_indices:
        cameras.append(CameraInfo(
            index=idx,
            name=f"Camera {idx}",
            available=True
        ))

    return cameras


def enumerate_cameras() -> list[CameraInfo]:
    """
    Enumerate available cameras with names.

    Cross-platform function that dispatches to platform-specific implementations.

    Returns:
        List of CameraInfo objects
    """
    system = platform.system()

    if system == "Darwin":
        return _enumerate_macos()
    elif system == "Windows":
        return _enumerate_windows()
    elif system == "Linux":
        return _enumerate_linux()
    else:
        log_info(f"Unknown platform '{system}', using fallback enumeration")
        return _enumerate_fallback()


def get_available_cameras() -> list[dict]:
    """
    Get list of available cameras for API response.

    Returns:
        List of dicts with 'index', 'name', 'available' keys
    """
    cameras = enumerate_cameras()
    return [
        {"index": c.index, "name": c.name, "available": c.available}
        for c in cameras
    ]


def validate_camera_name(device_id: int, expected_name: Optional[str]) -> Optional[str]:
    """
    Validate that a camera index matches the expected name.

    Args:
        device_id: Camera index to validate
        expected_name: Expected camera name (from saved config)

    Returns:
        Warning message if mismatch, None if valid or no expected name
    """
    if not expected_name:
        return None

    cameras = enumerate_cameras()

    for cam in cameras:
        if cam.index == device_id:
            if cam.name != expected_name:
                return (
                    f"Camera {device_id} is now '{cam.name}' "
                    f"(was '{expected_name}'). Camera indices may have changed."
                )
            return None

    # Camera index not found at all
    return f"Camera {device_id} ('{expected_name}') is no longer available."
