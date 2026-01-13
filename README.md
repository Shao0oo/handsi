# Handsi — Contactless Desktop Control

Control your Mac using hand gestures — no mouse, no keyboard needed.

Handsi is a local, privacy-first gesture control system that tracks your hands via webcam and maps gestures to OS actions like switching desktops, scrolling, clicking, and window management.

---

## Quick Start

#### For Users:

**[Installation Guide](INSTALLATION.md)** - Download the DMG and start using Handsi in 2 minutes

#### For Developers:

**[Developer Installation](docs/dev/DEVELOPER_INSTALLATION.md)** - Build from source or contribute

---

## Features:

- ✅ Real-time hand tracking (single webcam)
- ✅ Gesture toggle: enable/disable control mode
- ✅ Configurable gesture → action mapping
- ✅ Actions:
  - Mouse movement
  - Click and drag
  - Scroll (vertical/horizontal)
  - Zoom in/out
  - Desktop switching (next/previous workspace)
  - Window management (minimize/maximize/app switcher)
  - Volume control

**Planned:**
- Head/body tracking (active vs inactive hands)
- Adjustable signals learned over time
- Voice + motion labeling
- Onboarding and calibration
- Gesture combos (temporal and physical grammar)

---

## Goals

- **Mobility-first:** Control the screen while walking/standing
- **Low cognitive load:** Small set of reliable gestures with clear activation
- **Adaptable signals:** Use voice + motion to program personalized gestures over time

---

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **macOS** | ✅ Supported | Apple Silicon (M1/M2/M3) and Intel |
| **Linux** | ⏳ Planned | Future release |
| **Windows** | ⏳ Planned | Future release |

---

## Documentation

### User Documentation
- **[Installation Guide](INSTALLATION.md)** — Download DMG and install

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

## Screenshots

*Coming soon*

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
