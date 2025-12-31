# Handsi — Contactless Desktop Control

Handsi is a local, background-running gesture control system that lets you operate your computer without touching the mouse/keyboard. It tracks your hands via a webcam or camera, recognizes gestures, and maps them to OS actions like switching desktops, scrolling, clicking, and window management.

## Goals
- **Mobility-first:** control the screen while walking/standing.
- **Low cognitive load:** small set of reliable gestures + clear activation latch.
- **Adaptible signals** use of voice + motion signal to program your personal signals over time.

## Getting Started

- 📦 [Installation Guide](docs/INSTALLATION.md) — Set up your development environment
- 🔨 [Build Instructions](docs/BUILD.md) — Create standalone executables
- 📚 [Documentation](#documentation) — Architecture and implementation details

---

## Features (Minimal Viable Product MVP)
- Real-time hand tracking (single webcam)
- Gesture toggle: enable/disable control mode via an intentional gesture
- Gesture → action mapping (YAML config or alternative suggestion)
- Actions:
  - zoom in and out (for text)
  - mouse move
    - click, drag (optional)
  - scroll
  - next/previous desktop (workspace)
  - minimize / maximize / app switch (i.e. pressing windows key or F3 on mac)

## Planned
- Head/torso relative to hand to potentially determine active vs inactive hands
- Adjustable signals, potentially learned over time
  - Initially use audio + motion signal
  - Then just motion signal
- Onboarding + calibration for different users
- “Gesture combos” (temporal and physical grammar)

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design, data flow, and module organization
- [Implementation Details](docs/IMPLEMENTATION.md) — Development details and technical specifications
- [Build Guide](docs/BUILD.md) — Creating standalone executables and distribution packages
- [macOS Setup](docs/SETUP_MACOS.md) — Platform-specific setup and permissions