# implementation.md — Phase 1 (CLI MVP)

## Purpose
Phase 1 delivers a **command-line** Handsi that:
- Captures webcam frames
- Tracks hands (optionally head/pose later)
- Decodes a small, reliable gesture set
- Applies **safety latch + debouncing**
- Executes a minimal set of desktop actions
- Runs locally with a debug preview window and logs

**No tray app. No autostart. No teaching mode.** Just a solid engine.

---

## Phase 1 Scope

### Must-have
- Real-time webcam capture (OpenCV)
- Hand landmark tracking (MediaPipe Hands)
- Gesture decoding (rule-based)
- Temporal smoothing + state machine (latch, cooldown)
- Action execution (macOS first; leave adapter interface for Linux)
- CLI entrypoint with:
  - `--preview` (overlay window)
  - `--debug` (prints gesture states / confidence)
  - `--config path`

### Nice-to-have (still Phase 1 if easy)
- Basic head pose/face detection overlay (no actions yet)
- JSON/TOML config instead of YAML (if you want better validation)

### Non-goals
- System tray UI
- Run-on-startup
- Gesture teaching / personalization
- Complex window management beyond a couple OS actions

---

## Threading Architecture

Phase 1 uses a **5-thread pipeline** for maximum modularity and CPU efficiency:

### Thread Breakdown

**Thread 1: Capture**
- Reads camera frames at **adaptive FPS** (1-10 Hz based on activity)
- Pushes to `FrameQueue` (bounded size)
- Drops frames if queue is full (frame-skipping backpressure)
- Listens to shared `RuntimeState` for FPS adjustments

**Thread 2: Tracking + Features (inline)**
- Pops from `FrameQueue`
- MediaPipe Hands tracking → landmarks
- Feature extraction (inline, same thread)
- Detects activity level → updates shared `RuntimeState.activity_level`
- Pushes feature vectors to `FeatureQueue`
- Controls own processing rate based on activity

**Thread 3: Gesture Inference**
- Pops from `FeatureQueue`
- Rule-based gesture detection (pinch, fist, swipe, etc.)
- Temporal smoothing over sliding window
- Pushes recognized gestures to `GestureEventQueue`

**Thread 4: Action Executor**
- Pops from `GestureEventQueue`
- **State machine** (latch, debounce, cooldown) lives here
- Maps gestures → actions via config
- Executes OS actions (macOS adapters)
- Updates `RuntimeState.last_gesture_time` on execution

**Thread 5: Preview Window (optional, `--preview` only)**
- Receives frame copies + overlay data (landmarks, gesture labels)
- Renders debug visualization in OpenCV window
- Non-blocking updates (drops frames if rendering falls behind)

### Inter-Thread Communication

All queues use `queue.Queue` (thread-safe, bounded):
- **FrameQueue**: max 2 frames (drop oldest on overflow)
- **FeatureQueue**: max 5 feature vectors
- **GestureEventQueue**: max 10 events

**Shared RuntimeState** (thread-safe with locks):
```python
@dataclass
class RuntimeState:
    activity_level: ActivityLevel  # IDLE | ATTENTIVE | ACTIVE
    current_fps: int               # 1-10 Hz
    last_gesture_time: float       # timestamp of last executed action
    system_active: bool            # global enable/disable flag
```

---

## Adaptive FPS Control

The system **dynamically adjusts capture/tracking rate** to minimize CPU usage when idle:

### Activity Levels

| Level | FPS | Trigger Condition |
|-------|-----|-------------------|
| **IDLE** | 1-2 Hz | No hands detected for >3 seconds |
| **ATTENTIVE** | 5 Hz | Hands detected, no gesture in last 2 seconds |
| **ACTIVE** | 10 Hz | Gesture detected/executing in last 1 second |

### Control Flow

1. **Tracking thread** detects hand presence after MediaPipe processing
2. Updates `RuntimeState.activity_level` based on:
   - Hand detection (present/absent)
   - Time since last gesture (`last_gesture_time`)
3. **Capture thread** reads `RuntimeState.current_fps` before each iteration
4. Adjusts sleep time: `sleep(1.0 / current_fps)`

### Benefits

- **CPU efficiency**: 80-90% reduction in idle CPU usage
- **Responsiveness**: Ramps up to 10 Hz within 100-200ms of detecting activity
- **Smooth transitions**: Hysteresis prevents rapid FPS oscillation

---

## Queue Strategy & Backpressure

### Frame-Skipping at Source

When `FrameQueue` is full:
- Capture thread **drops the current frame** (doesn't block)
- Logs warning: `CAP-002: Frame dropped (queue full)`
- Continues capturing at target FPS

### Why Not Block?

Blocking would cause:
- Camera buffer buildup (stale frames)
- Cascade delays through entire pipeline
- Unpredictable latency

Frame-skipping ensures:
- Always processing **fresh** frames
- Bounded memory usage
- Graceful degradation under load

---

## Error Code Taxonomy

Each layer has a unique prefix for debugging:

| Prefix | Layer | Example Errors |
|--------|-------|----------------|
| **CAP-xxx** | Capture | `CAP-001`: Camera open failed<br>`CAP-002`: Frame dropped (queue full)<br>`CAP-003`: Invalid frame dimensions |
| **TRK-xxx** | Tracking | `TRK-001`: MediaPipe init failed<br>`TRK-002`: Landmark detection timeout<br>`TRK-003`: Invalid hand pose |
| **FEA-xxx** | Features | `FEA-001`: Feature extraction failed<br>`FEA-002`: Insufficient landmarks<br>`FEA-003`: Normalization error |
| **GES-xxx** | Gestures | `GES-001`: Unknown gesture type<br>`GES-002`: Confidence below threshold<br>`GES-003`: Temporal window incomplete |
| **ACT-xxx** | Actions | `ACT-001`: Action mapping not found<br>`ACT-002`: OS adapter failed<br>`ACT-003`: Permission denied (accessibility) |
| **GUI-xxx** | Preview | `GUI-001`: Window creation failed<br>`GUI-002`: Rendering timeout<br>`GUI-003`: Overlay data invalid |

### Logging Format

```
[2025-12-25 10:15:32] [ERROR] TRK-003: Invalid hand pose on frame 1234
[2025-12-25 10:15:33] [WARN]  CAP-002: Frame dropped (queue full, tracking lagging)
[2025-12-25 10:15:40] [INFO]  Activity level: IDLE → ATTENTIVE (hands detected)
```

---

## Configuration Structure

Phase 1 uses **YAML** for flexibility (can migrate to TOML/JSON later).

### `config/default.yaml`

```yaml
camera:
  device_id: 0
  resolution: [640, 480]
  # Adaptive FPS ranges
  fps_idle: 2         # Hz when no hands detected
  fps_attentive: 5    # Hz when hands present, no gesture
  fps_active: 10      # Hz during/after gesture execution

tracking:
  max_hands: 2
  min_detection_confidence: 0.5
  min_tracking_confidence: 0.5
  # Activity level transitions
  idle_timeout: 3.0        # seconds without hands → IDLE
  attentive_timeout: 2.0   # seconds without gesture → ATTENTIVE

gestures:
  # Debouncing: cooldown after gesture fires
  debounce_ms: 300          # ignore same gesture for 300ms after firing
  # Latch: cooldown for activation gesture
  latch_cooldown_ms: 500    # prevent rapid latch on/off
  # Temporal smoothing
  smoothing_window: 3       # frames to average over

actions:
  # Gesture → Action mappings (modular for future changes)
  mappings:
    pinch: click
    fist: drag_start
    open_palm: drag_end
    swipe_left: prev_desktop
    swipe_right: next_desktop
    two_finger_spread: zoom_in
    two_finger_pinch: zoom_out
    # Latch gesture (enables/disables control mode)
    thumbs_up: toggle_latch

system:
  log_level: INFO           # DEBUG | INFO | WARN | ERROR
  log_file: logs/handsi.log
  preview: false            # override with --preview
  debug: false              # override with --debug

macos:
  # macOS-specific settings
  accessibility_check: true  # verify permissions on startup
  scroll_speed: 10           # pixels per scroll event
  zoom_step: 0.1             # zoom increment (0.1 = 10%)
```

### Config Validation

- Loaded via `handsi/core/config.py`
- Pydantic models for validation (type safety, bounds checking)
- Errors logged as `CFG-xxx` if invalid

---

## Module Breakdown (Updated)

### Core Modules

**Capture** (`handsi/vision/capture.py`)
- `CaptureThread(threading.Thread)`: Webcam capture with adaptive FPS
- `get_frame()`: Non-blocking frame retrieval
- Error codes: `CAP-xxx`

**Tracking + Features** (`handsi/vision/tracking.py`)
- `TrackingThread(threading.Thread)`: MediaPipe processing + feature extraction (inline)
- `MediaPipeTracker`: Wrapper for MediaPipe Hands
- `extract_features(landmarks)`: Landmark → normalized feature vector
- Updates `RuntimeState.activity_level` based on detection
- Error codes: `TRK-xxx`, `FEA-xxx`

**Gestures** (`handsi/gestures/`)
- `rules.py`: Rule-based detector (pinch, fist, swipe, open palm)
- `infer.py`: `GestureInferenceThread` (pops features, detects gestures)
- `smoothing.py`: Temporal averaging over sliding window
- Error codes: `GES-xxx`

**Actions** (`handsi/actions/`)
- `executor.py`: `ActionExecutorThread` with **state machine** (latch, debounce)
- `mapping.py`: Loads gesture → action mappings from config
- `adapters/macos.py`: macOS action implementations (Quartz, Accessibility APIs)
- `adapters/linux.py`: Linux stub (Phase 2)
- Error codes: `ACT-xxx`

**Preview** (`handsi/ui/preview.py`)
- `PreviewThread(threading.Thread)`: OpenCV window rendering (optional)
- Receives frame copies + overlay data (landmarks, gesture labels, FPS)
- Non-blocking (drops frames if can't keep up)
- Error codes: `GUI-xxx`

**Core Infrastructure** (`handsi/core/`)
- `bus.py`: Queue definitions + `RuntimeState` class
- `config.py`: YAML loading + Pydantic validation
- `logging.py`: Structured logging with error code prefixes

**Entrypoint** (`handsi/main.py`)
- CLI argument parsing (`--preview`, `--debug`, `--config`)
- Thread lifecycle management (start, join, graceful shutdown)
- Signal handling (Ctrl+C)

---

## Deliverables (Acceptance Criteria)
You can run:

```bash
python -m handsi.main --preview --debug --config config/default.yaml
```
