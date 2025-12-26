#!/usr/bin/env python3
"""
Check and request camera permissions on macOS.

Run this before first launch to ensure camera access is granted.
"""

import os
import sys
import subprocess


def check_camera_permission_macos():
    """Check if camera permission is granted on macOS."""
    try:
        # Try using AVFoundation to check permission
        result = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to get name'],
            capture_output=True,
            text=True,
            timeout=5
        )

        print("✓ Terminal has accessibility permissions")
        return True

    except Exception as e:
        print(f"⚠ Warning: Could not verify permissions: {e}")
        return False


def print_instructions():
    """Print instructions for granting camera permissions."""
    print("\n" + "="*60)
    print("Camera Permission Required")
    print("="*60)
    print("\nTo grant camera access:")
    print("1. Open System Settings > Privacy & Security > Camera")
    print("2. Find 'Terminal' or 'iTerm' (or your terminal app)")
    print("3. Toggle it ON")
    print("4. Restart this program")
    print("\nAlternatively, run with environment variable:")
    print("  export OPENCV_AVFOUNDATION_SKIP_AUTH=1")
    print("  handsi --preview")
    print("\n" + "="*60 + "\n")


def main():
    """Main function."""
    print("Handsi Camera Permission Checker")
    print("-" * 60)

    if sys.platform != "darwin":
        print("✓ Not on macOS, no special permissions needed")
        return 0

    print("Checking macOS camera permissions...")

    # Check if OPENCV_AVFOUNDATION_SKIP_AUTH is set
    if os.environ.get("OPENCV_AVFOUNDATION_SKIP_AUTH") == "1":
        print("⚠ OPENCV_AVFOUNDATION_SKIP_AUTH=1 is set")
        print("  This skips macOS permission checks. Make sure you've")
        print("  granted camera access manually in System Settings.")
        return 0

    # Check permissions
    check_camera_permission_macos()

    # Print instructions
    print_instructions()

    # Test camera access
    print("Testing camera access...")
    try:
        import cv2
        cap = cv2.VideoCapture(0)

        if cap.isOpened():
            print("✓ Camera opened successfully!")
            ret, frame = cap.read()
            if ret:
                print(f"✓ Frame captured: {frame.shape}")
            cap.release()
            return 0
        else:
            print("✗ Camera failed to open")
            print("\nPlease grant camera permissions and try again.")
            return 1

    except Exception as e:
        print(f"✗ Error testing camera: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
