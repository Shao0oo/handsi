# Handsi — Contactless Desktop Control

Control your Mac using hand gestures — no mouse, no keyboard needed.

Handsi is a local, privacy-first gesture control system that tracks your hands via webcam and maps gestures to OS actions like switching desktops, scrolling, clicking, and window management.

---

## Quick Start

#### For Users:

**[Installation Guide](INSTALLATION.md)** - Download the DMG and start using Handsi in 2 minutes

**Connecting might take a minute** - initializing backend takes a long time.

#### For Developers:

**[Developer Installation](docs/dev/DEVELOPER_INSTALLATION.md)** - Build from source or contribute

#### Usage:

**[Usage Guide](docs/USAGE.md)** — guide to using Handsi

---

## Use Cases

### Reading papers away from the desk
Stand or walk around while reading on your screen. Control scrolling, zooming, changing tabs, and page navigation without being tethered to your desk.

### Watching videos while eating
Keep both hands free to eat while controlling playback, volume, and navigation with simple gestures.

### Hybrid control: one hand on trackpad, one hand gesturing
Use your trackpad for precise work with one hand, while your other hand handles clicking, scrolling, or switching desktops via gestures.

### Getting Handsi
Perfect for when you want to get handsi!

---

## Features:

- Real-time hand tracking (single webcam)
- Gesture toggle: enable/disable control mode
- Configurable gesture → action mapping
- Actions:
  - Mouse movement
  - Click
  - Scroll (vertical/horizontal)
  - Volume control
  - Zoom in/out
  - Tab through windows
  - Desktop switching (next/previous workspace)
  - Window management (view all windows)
  - Copy, paste, undo
  - etc...
- Habit detection 
  - Prevents abscentmindedly touching your face
  - Must be enabled in settings and gestures

**Planned:**
- Adjustable signals learned over time
- Voice + motion labeling
- Onboarding and calibration
- Gesture combos (temporal and physical grammar)

---

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **macOS** | ✅ Supported | Apple Silicon and Intel |
| **Linux** | ⏳ Planned | Future release |
| **Windows** | ⏳ Planned | Future release |

---

## Documentation

### User Documentation
- **[Installation Guide](INSTALLATION.md)** — Download DMG and install
- **[Usage Guide](docs/USAGE.md)** — How to use gestures and configure settings

### Developer Documentation
- **[Developer Installation](docs/dev/DEVELOPER_INSTALLATION.md)** — Set up dev environment
- **[Build Guide](docs/dev/BUILD.md)** — Build from source
- **[Release Guide](docs/dev/RELEASE.md)** — Create GitHub releases
- **[Tauri Guide](docs/dev/TAURI.md)** — Tauri architecture and migration
- **[Implementation Details](docs/dev/IMPLEMENTATION.md)** — Technical specifications

### Reference Documentation
- **[Architecture](docs/ARCHITECTURE.md)** — System design and data flow

---

## Tech Stack

- **Frontend:** HTML/CSS/JavaScript (Tauri WebView)
- **GUI Framework:** Tauri (Rust)
- **Backend:** Python 3.11
- **Computer Vision:** MediaPipe, OpenCV
- **Platform Integration:** PyObjC (macOS)

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes following [CLAUDE.md](CLAUDE.md) guidelines
4. Commit: `git commit -m "Add my feature"`
5. Push: `git push origin feature/my-feature`
6. Open a Pull Request

---

## License

*License information to be added*

---

## Questions or Issues?

- **[Report an Issue](https://github.com/Shao0oo/handsi/issues)**
- **[View Documentation](docs/)**

---

**Built with [Tauri](https://tauri.app) + Python + MediaPipe**
