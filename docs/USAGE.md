# Handsi Usage Guide

Control your Mac using hand gestures — no mouse, no keyboard needed.

## Prerequisites:

Install Handsi according to the **[Installation Guide](../INSTALLATION.md)**

## Table of Contents

- [Getting Started](#getting-started)
- [How to Position The Environment](#how-to-position-the-environment)
- [Understanding the Interface](#understanding-the-interface)
- [Available Gestures](#available-gestures)
- [Custom Configuration](#custom-configuration)
- [Troubleshooting](#troubleshooting)

## Getting Started

### Press Start Detection! Thats it! 

<details>
<summary>Toggling Gesture Control</summary>
To disable gesture control, use the **Thumbs Down** gesture:
- Extend your thumb downward
- Keep other fingers curled

To re-enable gesture control, use **Thumbs Up** gesture:
- Extend your thumb upward
- Keep other fingers curled
</details>


## How to Position the Environment

### Camera Setup

- Position your camera so it has a clear view of your hands
    - **Distance doesn't matter** — gestures are scale-invariant
- Ensure good lighting for accurate hand tracking

### Hand Placement

- Position hands IN VIEW of the camera
- Distant independent
  - All gesture thresholds are normalized by hand size

## Understanding the Interface

Handsi has four main pages accessible via tabs at the top:

### Dashboard
---

**What it shows:**
- **Detection Status**: Running or Stopped
- **FPS**: Current frame rate (higher = more responsive)
- **Activity Level**: IDLE, ATTENTIVE, or ACTIVE
- **Gesture Control**: Enabled or Disabled (toggled via Thumbs Up/Down)
- **Frame Counts**: Captured vs Processed

**Controls:**
- **Start Detection**: Begin hand tracking and gesture recognition
- **Stop Detection**: Pause all tracking

### Settings
---

Configure how Handsi behaves. Settings are organized into sections:

#### General Settings (Always Visible)

**Camera Device:**
- Select which camera to use (0 = default, usually built-in webcam)
- Change if you have multiple cameras
  - This disables gesture control
  - Re-enable using thumbs up

**Mouse Sensitivity:**
- Controls how fast the cursor moves relative to hand movement
- Higher = faster cursor movement
- Default: `0.5`

**Mirror X-axis:**
- When enabled, horizontal movement is mirrored (natural camera perspective)
- Leave this ON for intuitive control
- Turn OFF if you pilot helicopters

#### Advanced Settings (Collapsible)

<details>
<summary>Click "Advanced Settings" to expand:</summary>

**Mouse Control:**
- **Smoothing**: Reduces jitter (0 = raw input, 1 = maximum smoothing)
- **Dead Zone**: Minimum movement to register (prevents tiny jitters)

**Scroll Control:**
- **Scroll Sensitivity**: How fast scrolling responds to hand movement
- **Scroll Dead Zone**: Minimum movement to trigger scroll
- **Invert Scroll Direction**: Natural vs traditional scrolling

**Gesture Detection:**
- **Pinch Threshold**: Distance for pinch gestures (lower = more sensitive)
- **Fist Threshold**: How tightly fingers must curl
- **Swipe Velocity**: Speed required to trigger swipe
- **Open Hand Spread**: Minimum finger spread for open hand
- **Thumbs Vertical Distance**: Minimum vertical distance for thumbs up/down

**Timing:**
- **Debounce (ms)**: Cooldown after gesture fires (prevents rapid repeat)
- **Latch Cooldown (ms)**: Cooldown for thumbs up/down toggle
- **Smoothing Window**: Number of frames to average for gesture detection

</details>

### Gestures - Customize Handsi
---

**What it shows:**
- All available gestures and their mapped actions
- Enabled gestures appear first, unmapped gestures are grayed out

**How to use:**
- Click the dropdown next to any gesture to change its action
- Select "-- None --" to disable a gesture
- Changes apply immediately and are saved automatically

### Info
---

**What it shows:**
- **Camera**: Device ID, resolution, FPS range
- **System**: Platform, OS version, Python version
- **Permissions**: Accessibility status (required for gesture control)
- **Frames Information**: Real-time capture and processing counts
- **About**: Project description

## Available Gestures

### Hand Gestures
---

| Gesture | How to Perform | Default Action |
|---------|---------------|----------------|
| **Open Hand** | All 5 fingers extended and facing camera | Mouse Movement |
| **Index Pinch** | Thumb + index finger touching | Left Click |
| **Two Finger Pinch** | Thumb + index + middle touching | Double Click |
| **Middle Pinch** | Thumb + middle finger touching | Right Click |
| **Ring Pinch** | Thumb + ring finger touching | Continuous Volume Control |
| **Two Fingers Point** | Index + middle extended, others closed | Continuous Scroll |
| **Thumbs Up** | Thumb up, others closed | Enable Gesture Control |
| **Thumbs Down** | Thumb down, others closed | Disable Gesture Control |
| **Two Hands Pinch** | Both hands making index pinch | Continuous Zoom |

### Notes:
- **Continuous gestures** (mouse, scroll, zoom, volume) stay active while you hold the gesture
- **Single gestures** (click, double-click) fire once per gesture (with debounce)
- All gestures can be remapped in the Gestures tab


## Custom Configuration

### Config File Location
---

User settings are stored in:
```
~/.handsi/config.yaml
```

### Editing Config Manually
---

While you can edit settings via the UI, you can also edit the config file directly for more fine grain control:

```bash
# Open config in your editor
nano ~/.handsi/config.yaml
# or
code ~/.handsi/config.yaml
```


## Troubleshooting

### Gestures not triggering
---

**Check:**
1. Is detection running? (Dashboard → Start Detection)
2. Is gesture control enabled? (Thumbs Up gesture)
3. Is the gesture mapped? (Gestures tab)
4. Are thresholds too strict? (Settings → Advanced → Gesture Detection)


### Cursor movement is jittery
---

**Fix:**
- Increase smoothing (Settings → Mouse Control → Smoothing)
- Increase dead zone (Settings → Mouse Control → Dead Zone)
- Increase FPS in config file
- Check FPS on Dashboard (low FPS causes jitter)


### Gestures fire too frequently
---

**Fix:**
- Increase debounce time (Settings → Timing → Debounce)
- Increase gesture thresholds (Settings → Gesture Detection)


### Camera not detected
---

**Check:**
1. Camera permissions granted? (Info tab → Permissions)
2. Is another app using the camera? (Zoom, Skype, etc.)
3. Try different camera device (Settings → Camera Device)

**Fix:**
```bash
# List available cameras on macOS
system_profiler SPCameraDataType
```


### Accessibility permissions not working
---

**On macOS:**
1. Open **System Settings → Privacy & Security → Accessibility**
2. Remove Handsi from the list (click the minus button)
3. Quit and relaunch Handsi
4. Grant permissions when prompted

**After updating Handsi:**
- Always remove old permissions before reinstalling
- See [INSTALLATION.md](../INSTALLATION.md#reinstallation-or-updating-to-newer-release)

## Need Help?

- **Report Issues**: [GitHub Issues](https://github.com/Shao0oo/handsi/issues)
- **Installation Guide**: [INSTALLATION.md](../INSTALLATION.md)
- **Developer Docs**: [docs/dev/](dev/)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
