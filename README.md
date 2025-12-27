# Handsi (Alternatives: AirDesk, AirCursor) — Contactless Desktop Control (Hands + Head + Body)

Handsi is a local, background-running gesture control system that lets you operate your computer without touching the mouse/keyboard. It tracks your hands via a webcam or camera, recognizes gestures, and maps them to OS actions like switching desktops, scrolling, clicking, and window management.

## Goals
- **Mobility-first:** control the screen while walking/standing.
- **Low cognitive load:** small set of reliable gestures + clear activation latch.
- **Adaptible signals** use of voice + motion signal to program your personal signals over time. 

---

## Features (Minimal Viable Product MVP)
- Real-time hand tracking (single webcam)
- Gesture toggle: enable/disable control mode via an intentional gesture
- Gesture → action mapping (YAML config or alternative suggestion)
- Actions:
  - zoom in and out (for text)
  - mouse move (general area vs specific point depending on system stability)
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

## Architecture

```mermaid
flowchart TD
    A[Camera Frames + Mic Audio] --> B1[capture.video]
    A --> B2[capture.audio]

    B1 --> C1[FrameQueue]
    B2 --> C2[AudioQueue]

    C1 --> D[Tracking Module<br/>hands/pose/head]
    D --> E[LandmarkQueue]

    E --> F[Feature Extraction]
    F --> G[FeatureQueue]

    G --> H[Gesture Inference]
    H --> H1[Rules Backend MVP]
    H --> H2[Custom Model Backend<br/>Teaching Mode]
    H1 & H2 --> I[GestureEvents]

    C2 --> J[Teaching Supervisor]
    G --> J
    J --> J1[Voice/UI Labels]
    J --> J2[Record Feature Windows]
    J --> J3[Train/Update Model]
    J3 --> K[GestureModelStore]

    I --> L[Command Module]
    L --> L1[State Machine + Debouncing]
    L --> L2[Gesture → Action Mapping]
    L --> L3[OS Adapters macOS/Linux]

    L3 --> M[Mouse/Keyboard/Window Actions]

    style A fill:#e1f5ff
    style M fill:#ffe1e1
    style H fill:#fff4e1
    style J fill:#f0e1ff
```

**Data Flow Summary:**
1. **Input Layer**: Camera frames + optional mic audio
2. **Capture Layer**: Video/audio capture → queues
3. **Tracking Layer**: MediaPipe tracking → landmarks
4. **Feature Layer**: Normalized feature vectors + time windows
5. **Inference Layer**: Rule-based or ML model → gesture events
6. **Teaching Layer**: Voice/UI labeling + model training (parallel)
7. **Command Layer**: State management + action mapping + OS execution
8. **Output Layer**: System-level mouse/keyboard/window actions



### Modules

#### Capture
- `handsi/vision/capture.py` — webcam capture + FPS control
- `handsi/audio/capture.py` — microphone capture (optional; for Teaching Mode voice labels)

#### Tracking + Features
- `handsi/vision/tracking.py` — MediaPipe trackers (hands/pose/head) → landmarks
- `handsi/vision/features.py` — landmarks → normalized feature vectors + time-window assembly

#### Gestures
- `handsi/gestures/rules.py` — rule-based gesture detection (pinch, fist, swipe, open palm)
- `handsi/gestures/infer.py` — unified inference interface:
  - `RulesBackend`
  - `CustomModelBackend` (trained gestures)
- `handsi/gestures/state.py` — temporal smoothing, latch, combos, debouncing, cooldowns

#### Teaching Mode (Phase 3)
- `handsi/teach/teacher.py` — orchestrates teach sessions (start/stop, record, commit)
- `handsi/teach/labeling.py` — voice label parsing and/or UI label selection
- `handsi/teach/dataset.py` — stores labeled examples (feature windows + metadata)
- `handsi/teach/train.py` — trains/updates model (kNN/DTW → later small NN)
- `handsi/teach/model_store.py` — loads/saves versioned models + schema

#### Actions
- `handsi/actions/executor.py` — executes high-level actions (scroll, zoom, desktop switch)
- `handsi/actions/mapping.py` — gesture → action mapping layer (YAML/TOML/JSON)
- `handsi/actions/adapters/macos.py` — macOS adapter (Quartz / Accessibility APIs)
- `handsi/actions/adapters/linux.py` — Linux adapter (uinput/evdev/xdotool backend)

#### UI (Phase 2)
- `handsi/ui/tray.py` — tray app (toggle active mode, status, optional preview)
- `handsi/ui/teach_panel.py` — Teaching Mode panel (label, record, save, test)

#### Core
- `handsi/core/bus.py` — queues/events + shared runtime state
- `handsi/core/config.py` — config loading + validation
- `handsi/main.py` — entrypoint (tray vs headless)
- `handsi/logging.py` — structured logging + debug toggles

---

## Tech Stack
- Python 3.11+
- OpenCV (camera capture)
- MediaPipe (hand/pose/head tracking + optional gesture recognizer)
- pynput or PyAutoGUI (input injection)
- PySide6 (system tray UI)

Notes:
- macOS requires Accessibility permissions for input control.
- Windows/Linux may require additional permissions depending on backend.

---

## Installation

See [INSTALLATION.md](docs/INSTALLATION.md) for setup instructions.