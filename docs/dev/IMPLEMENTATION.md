# implementation.md — Phase 2

## Purpose

Handsi is a **contactless desktop control** application that:
- Captures webcam frames and tracks hands/face via MediaPipe
- Decodes gestures using rule-based detection with hand-scale normalization
- Applies safety controls (latch, debouncing, cooldown)
- Executes OS-level actions (mouse, keyboard, scroll, zoom, volume, desktop switching)
- Runs as a **Tauri desktop app** (Rust frontend + Python backend via IPC)
- Includes habit awareness (facial contact alerts)

Phase 1 (CLI MVP) is complete. Phase 2 focuses on cross-platform expansion, AI/learning features, and custom gesture support.

---

## Architecture Overview

Handsi uses a **dual-process architecture**:

```
┌─────────────────────────────┐        ┌──────────────────────────────┐
│  Tauri App (Rust)           │        │  Python Backend              │
│                             │        │                              │
│  - Desktop UI (WebView)     │◄──────►│  - Webcam capture (OpenCV)   │
│  - Action execution         │  IPC   │  - Hand tracking (MediaPipe) │
│  - Platform adapters        │ (JSON) │  - Gesture inference         │
│    (CGEvent, Win32, X11)    │        │  - State machine             │
│  - Window management        │        │  - Action handler logic      │
│                             │        │                              │
└─────────────────────────────┘        └──────────────────────────────┘
```

**Python** handles all vision, tracking, and gesture logic. When an action needs to execute, the Python backend sends a JSON message to **Rust** via stdout. Rust receives the message and executes it through platform-specific adapters (CGEvent on macOS, Win32 on Windows, X11/Wayland on Linux).

### Why Rust executes actions

On macOS, TCC (Transparency, Consent, Control) grants Accessibility permissions per-process. The Tauri app (Rust binary) has permission, but the Python sidecar subprocess does not. Moving action execution to Rust solves this permission boundary.

### IPC Protocol

All communication is JSON over stdin/stdout:

**Command** (Rust → Python):
```json
{"command": "start", "args": {}, "request_id": "123-start"}
```

**Response** (Python → Rust):
```json
{"success": true, "data": {"status": "running"}, "request_id": "123-start"}
```

**Action** (Python → Rust, fire-and-forget):
```json
{"type": "action", "action": "mouse_move_normalized", "x": 0.5, "y": 0.3}
```

---

## Threading Architecture

The Python backend uses a **5-thread pipeline**:

### Thread Breakdown

**Thread 1: Capture** (`src/handsi/vision/capture.py`)
- Reads camera frames at **adaptive FPS** (2–60 Hz based on activity)
- Pushes to `FrameQueue` (bounded, max 2)
- Drops frames if queue is full (frame-skipping backpressure)
- Reads `RuntimeState.current_fps` to adjust sleep time

**Thread 2: Tracking + Features** (`src/handsi/vision/tracking.py`)
- Pops from `FrameQueue`
- MediaPipe Hands tracking → landmarks
- Feature extraction (inline, same thread)
- Detects activity level → updates `RuntimeState.activity_level`
- Pushes feature vectors to `FeatureQueue` (max 5)

**Thread 3: Gesture Inference** (`src/handsi/gestures/infer.py`)
- Pops from `FeatureQueue`
- Rule-based gesture detection via `GestureDetector`
- Temporal smoothing over sliding window
- Pushes recognized gestures to `GestureQueue` (max 10)
- Only detects gestures that have action mappings (performance optimization)

**Thread 4: Action Executor** (`src/handsi/actions/executor.py`)
- Pops from `GestureQueue`
- **State machine** (latch, debounce, cooldown)
- Maps gestures → actions via config
- Delegates to specialized handler classes
- Sends actions to Rust via **IPC adapter** (`src/handsi/actions/adapters/ipc.py`)
- Spawns two internal background threads:
  - **CursorInterpolator** (`src/handsi/actions/interpolation.py`) — smooth cursor movement at 60 Hz
  - **ScrollMomentum** (`src/handsi/actions/momentum.py`) — kinetic scrolling after gesture ends

**Thread 5: Preview Window** (optional, `--preview` only)
- Renders debug visualization in OpenCV window
- Displays hand landmarks, gesture labels, FPS
- Non-blocking (drops frames if rendering falls behind)

### Inter-Thread Communication

All queues use `queue.Queue` (thread-safe, bounded):
- **FrameQueue**: max 2 frames (drop oldest on overflow)
- **FeatureQueue**: max 5 feature vectors
- **GestureQueue**: max 10 events

**Shared RuntimeState** (`src/handsi/core/bus.py`, protected by `threading.RLock`):
```python
@dataclass
class RuntimeState:
    activity_level: ActivityLevel  # IDLE | ATTENTIVE | ACTIVE
    current_fps: int               # 2-60 Hz
    last_gesture_time: float       # timestamp of last executed action
    latch_active: bool             # gesture control enabled/disabled
    hand_scale: float              # current hand size (wrist to MCP)
    cursor_position: tuple         # normalized hand position [0,1]
    primary_hand: Optional[str]    # "Left" or "Right"
    shutdown_requested: bool       # graceful shutdown flag
```

### Queue Strategy & Backpressure

When `FrameQueue` is full, the capture thread **drops the current frame** (doesn't block). This ensures:
- Always processing **fresh** frames (no stale camera buffer buildup)
- Bounded memory usage
- Graceful degradation under load

### Adaptive FPS Control

| Level | FPS | Trigger |
|-------|-----|---------|
| **IDLE** | 2 Hz | No hands detected for >3 seconds |
| **ATTENTIVE** | 5 Hz | Hands detected, no gesture in last 2 seconds |
| **ACTIVE** | 60 Hz | Gesture detected/executing in last 1 second |

The tracking thread updates `RuntimeState.activity_level` based on hand presence and gesture timing. The capture thread reads `RuntimeState.current_fps` and adjusts its sleep accordingly.

---

## Error Code Taxonomy

Each layer has a unique prefix for debugging:

| Prefix | Layer | Example Errors |
|--------|-------|----------------|
| **CAP-xxx** | Capture | `CAP-001`: Camera open failed, `CAP-002`: Frame dropped (queue full), `CAP-003`: Invalid frame dimensions |
| **TRK-xxx** | Tracking | `TRK-001`: MediaPipe init failed, `TRK-002`: Landmark detection timeout, `TRK-003`: Invalid hand pose |
| **FEA-xxx** | Features | `FEA-001`: Feature extraction failed, `FEA-002`: Insufficient landmarks, `FEA-003`: Normalization error |
| **GES-xxx** | Gestures | `GES-001`: Unknown gesture type, `GES-002`: Gesture queue full |
| **ACT-xxx** | Actions | `ACT-001`: Unexpected error in executor, `ACT-002`: OS adapter failed, `ACT-003`: Invalid action in config, `ACT-004`: Adapter init failed |
| **GUI-xxx** | Preview | `GUI-001`: Window creation failed, `GUI-002`: Rendering timeout |
| **CFG-xxx** | Configuration | `CFG-001`: Config file not found, `CFG-002`: Validation error, `CFG-003`: Invalid value |
| **ALT-xxx** | Alerts | `ALT-001`: Audio alert failed |

### Logging Format

```
[2025-12-25 10:15:32] [ERROR] TRK-003: Invalid hand pose on frame 1234
[2025-12-25 10:15:33] [WARN]  CAP-002: Frame dropped (queue full, tracking lagging)
[2025-12-25 10:15:40] [INFO]  Activity level: IDLE → ATTENTIVE (hands detected)
```

---

## Adding New Gestures

This section walks through every file that needs changes when adding a new gesture. Follow each step in order.

### Step 1: Register the gesture

**File:** `src/handsi/core/registry.py`

Add your gesture name (alphabetically) to `AVAILABLE_GESTURES`:

```python
AVAILABLE_GESTURES = [
    # ... existing gestures ...
    "my_new_gesture",  # ← add here
    # ...
]
```

This list is the source of truth. The UI and config validation reference it.

### Step 2: Implement detection logic

**File:** `src/handsi/gestures/rules.py`

Add a detection method to the `GestureDetector` class:

```python
def _detect_my_new_gesture(self, lm: list) -> Optional[tuple[str, float, dict]]:
    """
    Detect my_new_gesture from hand landmarks.

    Args:
        lm: List of 21 (x, y, z) tuples for hand landmarks

    Returns:
        (gesture_name, confidence, metadata) or None
    """
    hand_scale = self._get_hand_scale(lm)
    if hand_scale < 1e-6:
        return None

    # Example: check distance between two landmarks
    distance = self._normalized_distance(lm[4], lm[8], hand_scale)

    if distance < self.my_gesture_threshold:
        confidence = 1.0 - (distance / self.my_gesture_threshold)
        position = lm[9][:2]  # middle MCP as hand center
        return ("my_new_gesture", confidence, {
            "position": position,
            "hand_scale": hand_scale,
            "distance": distance
        })
    return None
```

**Key patterns:**
- Always normalize distances using `_get_hand_scale()` (wrist-to-middle-MCP distance). This makes detection work at any distance from the camera.
- Return format is always `(gesture_name: str, confidence: float, metadata: dict)`.
- Confidence must exceed `self.confidence_threshold` (default 0.7) to fire.
- Include `position` and `hand_scale` in metadata — the action system uses these.

### Step 3: Register in the detector loop

**Same file:** `src/handsi/gestures/rules.py`, in `detect_gestures()`

Add to the `single_hand_detectors` list (or `two_hand_detectors` for two-hand gestures):

```python
single_hand_detectors = [
    # ... existing ...
    ("my_new_gesture", lambda: self._detect_my_new_gesture(lm)),
]
```

For two-hand gestures:
```python
two_hand_detectors = [
    # ... existing ...
    ("my_two_hand_gesture", lambda: self._detect_my_two_hand_gesture(lm_left, lm_right)),
]
```

### Step 4: Add config threshold (if needed)

**File:** `config/default.yaml`

Add threshold under `gestures:`:
```yaml
gestures:
  my_gesture_threshold: 0.25  # normalized distance threshold
```

**File:** `src/handsi/core/config.py`

Add the field to `GestureConfig`:
```python
class GestureConfig(BaseModel):
    # ... existing fields ...
    my_gesture_threshold: float = Field(default=0.25)
```

Then use `self.my_gesture_threshold` in the `GestureDetector.__init__()` parameter list and the detection method.

### Step 5: Map to an action

**File:** `config/default.yaml`

Add under `actions.mappings:`:
```yaml
actions:
  mappings:
    my_new_gesture: click  # or any existing action
```

You can map to an existing action or create a new one (see next section).

### Summary: Files touched for a new gesture

| Step | File | Change |
|------|------|--------|
| 1 | `src/handsi/core/registry.py` | Add to `AVAILABLE_GESTURES` |
| 2 | `src/handsi/gestures/rules.py` | Add `_detect_*()` method |
| 3 | `src/handsi/gestures/rules.py` | Add to detector loop in `detect_gestures()` |
| 4 | `config/default.yaml` | Add threshold (optional) |
| 4 | `src/handsi/core/config.py` | Add to `GestureConfig` (optional) |
| 5 | `config/default.yaml` | Map gesture → action in `actions.mappings` |

---

## Adding New Actions

This section walks through every file that needs changes when adding a new action.

### Step 1: Register the action

**File:** `src/handsi/core/registry.py`

Add your action name (alphabetically) to `AVAILABLE_ACTIONS`:

```python
AVAILABLE_ACTIONS = [
    # ... existing actions ...
    "my_new_action",  # ← add here
    # ...
]
```

### Step 2: Add to the ActionName enum

**File:** `src/handsi/core/types.py`

Add a new enum value:

```python
class ActionName(str, Enum):
    # ... existing ...
    MY_NEW_ACTION = "my_new_action"
```

If the action is **continuous** (tracks state over time, no debouncing), also add it to `continuous_actions()`:

```python
@classmethod
def continuous_actions(cls) -> set["ActionName"]:
    return {cls.MOUSE_MOVE, cls.CONTINUOUS_SCROLL, ..., cls.MY_NEW_ACTION}
```

### Step 3: Create the handler

**File:** `src/handsi/actions/handlers/my_action.py` (new file)

Choose a base class:
- `ActionHandler` — generic base
- `DiscreteActionHandler` — one-shot actions (click, copy). `on_gesture_continue()` is a no-op.
- `ContinuousActionHandler` — stateful actions (scroll, zoom). Provides `reset_tracking()` hook.

```python
from handsi.actions.handlers.base import DiscreteActionHandler
from handsi.core.bus import GestureEvent


class MyNewActionHandler(DiscreteActionHandler):
    """Handler for my_new_action."""

    def execute(self, event=None) -> bool:
        """Execute the action."""
        return self.adapter.semantic_action("my_action")
```

For continuous actions, use `ContinuousActionHandler` and implement `on_gesture_start()`, `on_gesture_continue()`, `on_gesture_end()`:

```python
from handsi.actions.handlers.base import ContinuousActionHandler


class MyContinuousHandler(ContinuousActionHandler):
    def __init__(self, adapter, runtime_state, config):
        super().__init__(adapter, runtime_state)
        self._anchor = None

    def reset_tracking(self) -> None:
        self._anchor = None

    def on_gesture_start(self, event) -> None:
        super().on_gesture_start(event)
        self._anchor = event.metadata.get("position")

    def on_gesture_continue(self, event) -> None:
        # Calculate delta from anchor and execute
        pass

    def execute(self, event=None) -> bool:
        return True
```

### Step 4: Register in the executor

**File:** `src/handsi/actions/executor.py`

Import your handler and add it to `_create_handlers()`:

```python
from handsi.actions.handlers.my_action import MyNewActionHandler

# In _create_handlers():
ActionName.MY_NEW_ACTION: MyNewActionHandler(
    self.adapter,
    self.runtime_state
),
```

### Step 5: Map a gesture to the action

**File:** `config/default.yaml`

```yaml
actions:
  mappings:
    some_gesture: my_new_action
```

### Step 6: Implement on the Rust side (if new OS operation)

If your action uses an existing IPC method (e.g., `self.adapter.semantic_action()`, `self.adapter.keyboard_shortcut()`), no Rust changes are needed.

If you need a **new OS-level operation**:

**6a. Add to the ActionAdapter trait:**

**File:** `src-tauri/src/adapters/mod.rs`

```rust
pub trait ActionAdapter: Send {
    // ... existing methods ...
    fn my_new_operation(&self, param: f64) -> Result<(), String>;
}
```

**6b. Implement for each platform:**

- `src-tauri/src/adapters/macos.rs` — macOS implementation (CGEvent, AppleScript)
- `src-tauri/src/adapters/linux.rs` — Linux implementation (or stub)
- `src-tauri/src/adapters/windows.rs` — Windows implementation (or stub)

**6c. Add IPC routing:**

**File:** `src-tauri/src/main.rs`, in `process_action()`:

```rust
"my_new_operation" => {
    let param = msg.get("param").and_then(|v| v.as_f64()).unwrap_or(0.0);
    adapter.my_new_operation(param)
}
```

**6d. Add IPC method in Python:**

**File:** `src/handsi/actions/adapters/ipc.py`

```python
def my_new_operation(self, param: float) -> bool:
    return self._send_action({
        "action": "my_new_operation",
        "param": float(param)
    })
```

### Summary: Files touched for a new action

| Step | File | Change |
|------|------|--------|
| 1 | `src/handsi/core/registry.py` | Add to `AVAILABLE_ACTIONS` |
| 2 | `src/handsi/core/types.py` | Add to `ActionName` enum |
| 3 | `src/handsi/actions/handlers/<new>.py` | Create handler class |
| 4 | `src/handsi/actions/executor.py` | Register in `_create_handlers()` |
| 5 | `config/default.yaml` | Map gesture → action |
| 6a | `src-tauri/src/adapters/mod.rs` | Add to `ActionAdapter` trait (if new OS op) |
| 6b | `src-tauri/src/adapters/macos.rs` | macOS implementation (if new OS op) |
| 6b | `src-tauri/src/adapters/linux.rs` | Linux implementation (if new OS op) |
| 6b | `src-tauri/src/adapters/windows.rs` | Windows implementation (if new OS op) |
| 6c | `src-tauri/src/main.rs` | Add case in `process_action()` (if new OS op) |
| 6d | `src/handsi/actions/adapters/ipc.py` | Add IPC method (if new OS op) |

---

## Module Breakdown

### Python — Core (`src/handsi/core/`)

| File | Purpose |
|------|---------|
| `bus.py` | `RuntimeState`, queue definitions, `GestureEvent` dataclass |
| `config.py` | Pydantic config models, YAML loading and validation |
| `logging.py` | Structured logging with error code prefixes |
| `types.py` | `ActionName` enum, `GestureMetadata` TypedDict |
| `registry.py` | Master lists of available gestures and actions |
| `utils.py` | Path resolution, general utilities |

### Python — Vision (`src/handsi/vision/`)

| File | Purpose |
|------|---------|
| `capture.py` | `CaptureThread` — webcam capture with adaptive FPS |
| `tracking.py` | `TrackingThread` — MediaPipe tracking + feature extraction |

### Python — Gestures (`src/handsi/gestures/`)

| File | Purpose |
|------|---------|
| `rules.py` | `GestureDetector` — rule-based detection (1000+ lines) |
| `infer.py` | `GestureInferenceThread` — temporal smoothing + queue |
| `smoothing.py` | Sliding-window temporal averaging |

### Python — Actions (`src/handsi/actions/`)

| File | Purpose |
|------|---------|
| `executor.py` | `ActionExecutorThread` — main orchestrator |
| `state_machine.py` | `GestureStateMachine` — latch, debounce, cooldown |
| `interpolation.py` | `CursorInterpolator` — smooth 60 Hz cursor movement |
| `momentum.py` | `ScrollMomentum` — kinetic scrolling after gesture ends |
| `adapters/ipc.py` | `IPCAdapter` — fire-and-forget JSON to Rust |
| `adapters/base.py` | `ActionAdapter` base class (Python interface) |
| `handlers/base.py` | `ActionHandler`, `DiscreteActionHandler`, `ContinuousActionHandler` |
| `handlers/click.py` | Click, double-click, right-click handlers |
| `handlers/mouse.py` | Mouse movement handler |
| `handlers/scroll.py` | Scroll step + continuous scroll handlers |
| `handlers/zoom.py` | Zoom step + continuous zoom handlers |
| `handlers/volume.py` | Continuous volume handler |
| `handlers/tab.py` | Continuous tab switching handler |
| `handlers/desktop.py` | Desktop/workspace switching handler |
| `handlers/keyboard.py` | Copy, paste, undo handlers |
| `handlers/latch.py` | Enable/disable latch handlers |
| `handlers/alert.py` | Habit awareness alert handlers (visual + audio) |

### Python — UI (`src/handsi/ui/`)

| File | Purpose |
|------|---------|
| `controller.py` | Backend controller — orchestrates thread lifecycle |
| `ipc_server.py` | IPC command handler (stdin/stdout JSON protocol) |
| `preview.py` | OpenCV debug preview window |

### Python — Teach (`src/handsi/teach/`)

Scaffolded for Phase 3. Currently empty placeholders.

### Rust — Tauri App (`src-tauri/src/`)

| File | Purpose |
|------|---------|
| `main.rs` | Tauri app entry point, IPC handling, `process_action()` routing |
| `adapters/mod.rs` | `ActionAdapter` trait + `create_adapter()` factory |
| `adapters/macos.rs` | macOS adapter (CGEvent, AppleScript, multi-monitor) |
| `adapters/linux.rs` | Linux adapter (stub — Phase 2) |
| `adapters/windows.rs` | Windows adapter (stub — Phase 2) |

### Entrypoint (`src/handsi/main.py`)

- Parses CLI arguments (`--ipc`, `--cli`, `--preview`, `--config`)
- Starts thread pipeline via `controller.py`
- Signal handling (Ctrl+C → graceful shutdown)

---

## Configuration

All configuration lives in `config/default.yaml` and is validated by Pydantic models in `src/handsi/core/config.py`.

The config covers camera settings, tracking thresholds, gesture detection parameters, action mappings, mouse/scroll/zoom/volume/tab tuning, and habit awareness settings.

User-specific overrides can be placed in `~/.handsi/config.yaml`. See the default config file for all available options.

---

## How to Build and Run

### Prerequisites

```bash
conda activate handsi
pip install -e .
```

### Development Mode

```bash
npm run dev
# or
./scripts/dev-tauri.sh
```

This starts the Tauri app in dev mode, which spawns the Python backend as a subprocess:
```
python -m handsi.main --ipc stdio --config config/default.yaml
```

### Production Build

```bash
./scripts/build-tauri.sh
```

This:
1. Builds the Python backend with PyInstaller → `src-tauri/bin/handsi-backend`
2. Compiles the Rust/Tauri app
3. Creates `Handsi.app` bundle and `.dmg` installer

### Python-Only Preview (no actions)

For debugging hand tracking without the Tauri app:

```bash
conda activate handsi
python -m handsi.main --cli --preview
```

This runs the capture + tracking + gesture pipeline with a debug visualization window but **no action execution** (since actions require the Rust side for OS permissions).

---

## Phase 2 Roadmap

- **Cross-platform expansion** — implement Linux and Windows adapters (see next section)
- **Automatic gesture adding** — allow users to define custom gestures
- **AI and learning features** — ML-based gesture recognition alongside rules
- **Teaching mode** — record, label, and train custom gesture models (scaffolded in `src/handsi/teach/`)
- **Improved UI** — settings, gesture mapping editor, live feedback

---

## Cross-Platform Expansion

The Rust adapter architecture is designed for cross-platform support. The Python side is already fully platform-agnostic.

### Where to add Linux support

1. **`src-tauri/src/adapters/linux.rs`** — implement all `ActionAdapter` trait methods
   - Mouse: X11 via `XTest` extension, or `uinput`/`evdev` for Wayland
   - Keyboard: `xdotool` or `XTest`
   - Scroll: `XTest` scroll events
   - Desktop switching: `wmctrl` or D-Bus
   - Volume: `pactl` (PulseAudio) or `amixer` (ALSA)
   - Zoom: keyboard shortcuts (`Ctrl++`/`Ctrl+-`)

2. **`src-tauri/src/adapters/mod.rs`** — already wired via conditional compilation:
   ```rust
   #[cfg(target_os = "linux")]
   {
       let mut adapter = Box::new(linux::LinuxAdapter::new());
       adapter.initialize()?;
       Ok(adapter)
   }
   ```

3. **No Python changes needed** — all actions flow through `IPCAdapter` regardless of platform.

4. **CI/CD** — `.github/workflows/release.yml` needs Linux build targets (Ubuntu runner, AppImage/deb packaging).

### Where to add Windows support

1. **`src-tauri/src/adapters/windows.rs`** — implement all `ActionAdapter` trait methods
   - Mouse/Keyboard: Win32 `SendInput` API
   - Scroll: Win32 `mouse_event` with `MOUSEEVENTF_WHEEL`
   - Desktop switching: Virtual Desktop COM API
   - Volume: `IAudioEndpointVolume` COM interface
   - Zoom: keyboard shortcuts (`Ctrl++`/`Ctrl+-`)

2. **`src-tauri/src/adapters/mod.rs`** — already wired via conditional compilation.

3. **CI/CD** — needs Windows build targets (windows-latest runner, MSI/NSIS packaging).

### Platform adapter trait

All platform adapters must implement every method in `ActionAdapter` (`src-tauri/src/adapters/mod.rs`):

```rust
pub trait ActionAdapter: Send {
    fn initialize(&mut self) -> Result<(), String>;
    fn mouse_move(&self, x: f64, y: f64) -> Result<(), String>;
    fn mouse_move_normalized(&self, x_norm: f64, y_norm: f64) -> Result<(), String>;
    fn mouse_down(&self, x: f64, y: f64, button: u8) -> Result<(), String>;
    fn mouse_up(&self, x: f64, y: f64, button: u8) -> Result<(), String>;
    fn mouse_click(&self, x: f64, y: f64, button: u8) -> Result<(), String>;
    fn mouse_double_click(&self, x: f64, y: f64, button: u8) -> Result<(), String>;
    fn mouse_down_normalized(&self, x_norm: f64, y_norm: f64, button: u8) -> Result<(), String>;
    fn mouse_up_normalized(&self, x_norm: f64, y_norm: f64, button: u8) -> Result<(), String>;
    fn mouse_click_normalized(&self, x_norm: f64, y_norm: f64, button: u8) -> Result<(), String>;
    fn mouse_double_click_normalized(&self, x_norm: f64, y_norm: f64, button: u8) -> Result<(), String>;
    fn get_mouse_position_normalized(&self) -> Result<(f64, f64), String>;
    fn mouse_move_relative_normalized(&self, dx: f64, dy: f64) -> Result<(), String>;
    fn reset_cursor_tracking(&self) -> Result<(), String>;
    fn scroll(&self, dx: i32, dy: i32) -> Result<(), String>;
    fn key_press(&self, key_code: u16, modifiers: u64) -> Result<(), String>;
    fn switch_desktop(&self, direction: &str) -> Result<(), String>;
    fn set_volume(&self, delta: i32) -> Result<(), String>;
    fn keyboard_shortcut(&self, shortcut: &str) -> Result<(), String>;
    fn zoom(&self, direction: &str, step: f64) -> Result<(), String>;
    fn semantic_action(&self, name: &str) -> Result<(), String>;
    fn cleanup(&mut self);
}
```

The `create_adapter()` factory function uses `#[cfg(target_os = "...")]` to select the correct implementation at compile time.
