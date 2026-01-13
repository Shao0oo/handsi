# macOS Setup Guide

This guide covers macOS-specific setup for Handsi, including camera permissions.

## Prerequisites

- macOS 12.0 or later
- Python 3.11+
- Conda or venv

## Installation

1. **Clone the repository**
   ```bash
   cd ~/Desktop
   git clone https://github.com/Shao0oo/handsi.git handsi
   cd handsi
   ```

2. **Create conda environment**
   ```bash
   conda create -n handsi python=3.11
   conda activate handsi
   ```

3. **Install Handsi**
   ```bash
   pip install -e .
   ```

## Camera Permissions

macOS requires explicit permission to access the camera. There are two ways to handle this:

### Option 1: Grant Permissions (Recommended)

1. **Run the permission checker**
   ```bash
   python scripts/check_permissions.py
   ```

2. **Grant camera access**
   - Open **System Settings** > **Privacy & Security** > **Camera**
   - Find your terminal app (Terminal.app, iTerm2, etc.)
   - Toggle it **ON**

3. **Verify access**
   ```bash
   python scripts/check_permissions.py
   ```

   You should see:
   ```
   ✓ Camera opened successfully!
   ✓ Frame captured: (480, 640, 3)
   ```

### Option 2: Manual Environment Variable

If you've already granted camera access but OpenCV still fails, the environment variable is automatically set in `main.py`. No action needed.

## Running Handsi

```bash
# Activate environment
conda activate handsi

# Run with preview (shows camera + hand tracking)
handsi --preview

# Run with debug logging
handsi --preview --debug
```

## Troubleshooting

### Camera Not Opening

**Error:**
```
OpenCV: not authorized to capture video (status 0)
CAP-001: Failed to open camera 0
```

**Solutions:**

1. **Check camera permissions**
   ```bash
   python scripts/check_permissions.py
   ```

2. **Verify camera is not in use**
   - Close other apps using the camera (Zoom, FaceTime, etc.)
   - Check Activity Monitor for processes using "VDC" (Video Device Controller)

3. **Try different camera ID**
   Edit `config/default.yaml`:
   ```yaml
   camera:
     device_id: 1  # Try 1, 2, 3 if 0 fails
   ```

4. **Reset camera permissions**
   ```bash
   tccutil reset Camera
   ```
   Then re-grant permissions in System Settings.

### Preview Window Not Showing

**Error:**
```
GUI-001: Preview window error: Unknown C++ exception from OpenCV code
```

**Solution:**
This usually happens when camera access fails. Fix camera permissions first (see above).

### Permission Denied Errors

If you plan to use action execution (Phase 2), you'll need:

**Accessibility Permissions:**
1. System Settings > Privacy & Security > Accessibility
2. Add your terminal app
3. Toggle it ON

**Note:** Phase 1 (capture + tracking) doesn't need accessibility permissions yet.

## Development

### Reinstalling After Code Changes

```bash
pip install -e .
```

The `-e` flag installs in "editable" mode, so Python code changes take effect immediately without reinstalling.

### Checking Installation

```bash
# Verify installation
handsi --help

# Check from any directory
cd /tmp
handsi --help  # Should still work
```

## System Requirements

- **Camera:** Any USB or built-in webcam
- **RAM:** 2GB minimum (4GB recommended)
- **CPU:** Apple Silicon (M1/M2) or Intel x64
  - MediaPipe is optimized for Apple Silicon

## Performance Tips

1. **Close unnecessary apps** to free up camera resources
2. **Use lower resolution** if tracking is slow:
   ```yaml
   camera:
     resolution: [320, 240]  # Lower resolution = faster
   ```

3. **Adjust FPS ranges** in `config/default.yaml`:
   ```yaml
   camera:
     fps_idle: 1        # Lower for battery savings
     fps_active: 8      # Lower if CPU usage too high
   ```

## Next Steps

- See [IMPLEMENTATION.md](IMPLEMENTATION.md) for architecture details
- See [README.md](../README.md) for feature overview
- Try adjusting gesture sensitivity in `config/default.yaml`
