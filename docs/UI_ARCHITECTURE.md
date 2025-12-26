# UI Architecture - Phase 1 vs Phase 2+

This document explains the UI architecture evolution from Phase 1 (development) to Phase 2+ (production).

## Phase 1: OpenCV Preview in Main Loop

### Current Implementation

**Architecture:**
```
Main Thread:
  - Parse args, load config
  - Start capture thread
  - Start tracking thread
  - Initialize OpenCV window (if --preview)
  - Main loop:
      - Update preview (render frame)
      - Check for 'q' key
      - Sleep briefly
```

**Why This Approach?**
- ✅ **Works on macOS**: OpenCV windows must be created/updated on main thread
- ✅ **Simple**: No complex threading or event loops
- ✅ **Good for debugging**: Easy to see what's happening
- ✅ **Fast iteration**: Changes are immediately visible

**Limitations:**
- ❌ **Blocks main thread**: Preview rendering blocks other operations
- ❌ **No system tray**: Can't run in background
- ❌ **Limited UI**: Just a preview window, no controls
- ❌ **Not production-ready**: Users expect polished UI

### When to Use Phase 1 Approach
- Development and debugging
- Testing hand tracking algorithms
- Demonstrating proof-of-concept
- Quick iterations on gesture recognition

---

## Phase 2+: PySide6 System Tray UI

### Planned Implementation

**Architecture:**
```
Main Thread (Qt Event Loop):
  - Qt Application
  - System Tray Icon
  - Settings Dialog
  - Preview Widget (optional)

Worker Threads:
  - Capture Thread → FrameQueue
  - Tracking Thread → FeatureQueue
  - Gesture Thread → GestureQueue
  - Action Thread → OS API calls

Communication:
  - Qt Signals/Slots (thread-safe)
  - Queues for data flow
  - RuntimeState for shared state
```

**Why Qt/PySide6?**
- ✅ **Native system tray**: Run in background, minimize to tray
- ✅ **Cross-platform**: Works on macOS/Windows/Linux
- ✅ **Rich UI**: Settings dialogs, gesture mapping editor, etc.
- ✅ **Thread-safe**: Built-in signal/slot mechanism
- ✅ **Professional**: Polished, native-looking UI

### Phase 2 Features

**System Tray:**
- Icon with status indicator (idle/active/tracking)
- Right-click menu:
  - Toggle Active
  - Settings
  - Preview Window
  - Quit

**Settings Dialog:**
- Camera selection
- FPS ranges (idle/attentive/active)
- Gesture → Action mappings
- Enable/disable individual gestures
- Confidence thresholds

**Preview Widget (Optional):**
- Embedded Qt widget (not OpenCV window)
- Dockable/floating
- Can be hidden
- Shows landmarks + status

### Phase 3 Additions

**Teaching Mode Panel:**
- Record new gestures
- Voice labeling interface
- Test recorded gestures
- Save/load gesture models

**Gesture Editor:**
- Visual gesture → action mapper
- Timeline view for temporal gestures
- Combo gesture creator

---

## Migration Path

### Step 1: Keep Phase 1 (Current)
- Continue using OpenCV preview for development
- Focus on getting core features working (capture, tracking, gestures, actions)
- Use `--preview` flag for debugging

### Step 2: Implement Basic Qt Tray (Phase 2 Start)
- Create minimal PySide6 system tray
- Move to Qt event loop
- Keep worker threads (capture, tracking, gesture, action)
- Remove OpenCV preview entirely

### Step 3: Add Qt-based Preview (Phase 2)
- Create Qt widget for video display
- Use QImage/QPixmap instead of cv2.imshow()
- Render landmarks using QPainter
- Embeddable in main window or floating

### Step 4: Settings UI (Phase 2)
- Settings dialog with tabs
- YAML config → UI bindings
- Save/load configs
- Real-time config updates (no restart)

### Step 5: Teaching Mode (Phase 3)
- Teaching panel UI
- Voice/button-based labeling
- Progress indicators
- Model management

---

## Code Changes Required for Phase 2

### 1. Replace `main.py` Entrypoint

**Phase 1:**
```python
def main():
    # Parse args, load config
    # Start threads
    # Main loop with cv2.imshow()
```

**Phase 2:**
```python
def main():
    app = QApplication(sys.argv)

    # Create system tray
    tray = SystemTray()

    # Start worker threads
    capture_thread.start()
    tracking_thread.start()
    # ...

    # Enter Qt event loop
    sys.exit(app.exec())
```

### 2. Add Qt Signal Emitters

**Worker threads emit signals:**
```python
class TrackingThread(QThread):
    frame_ready = Signal(np.ndarray, list)  # frame, landmarks

    def run(self):
        # ... tracking code ...
        self.frame_ready.emit(frame, landmarks)
```

**UI receives signals:**
```python
class PreviewWidget(QWidget):
    def __init__(self):
        tracking_thread.frame_ready.connect(self.update_frame)

    def update_frame(self, frame, landmarks):
        # Convert to QPixmap, draw landmarks, display
```

### 3. Configuration UI

**Settings dialog:**
```python
class SettingsDialog(QDialog):
    def __init__(self, config: HandsiConfig):
        # Create tabs: Camera, Gestures, Actions, Advanced
        # Bind config values to widgets
        # Save button → write YAML
```

---

## Performance Considerations

### Phase 1 Performance
- **Preview rendering**: ~10-30ms per frame (acceptable for dev)
- **Main loop responsiveness**: Limited by preview update rate
- **CPU usage**: Higher (constant rendering)

### Phase 2 Performance
- **Qt rendering**: Similar to OpenCV, but more efficient
- **Main loop responsiveness**: Excellent (Qt event loop is optimized)
- **CPU usage**: Lower (only render when needed)
- **Battery impact**: Better (system can sleep between events)

---

## Recommendation

**For Now (Phase 1):**
- ✅ Use current OpenCV-in-main-loop approach
- ✅ Focus on getting tracking + gestures + actions working
- ✅ Use `--preview` for debugging only

**When to Migrate (Phase 2):**
- After Phase 1 is stable and tested
- When you need background operation (system tray)
- When implementing settings UI
- When preparing for user testing/deployment

**Migration Effort:**
- Small: ~2-3 days for basic Qt tray + preview
- Medium: ~1 week for full settings UI
- Large: ~2-3 weeks for teaching mode UI

---

## Questions?

**Q: Can I use both OpenCV and Qt preview?**
A: Not recommended. Choose one:
- Dev/debug → OpenCV (Phase 1)
- Production → Qt (Phase 2+)

**Q: Can Qt run in a thread?**
A: No. Qt event loop must run on main thread. Worker threads emit signals to main thread.

**Q: What about web UI (Flask/React)?**
A: Possible, but overkill for desktop app. Qt is better for native desktop integration (system tray, shortcuts, etc.).

**Q: How to handle preview during development in Phase 2?**
A: Qt preview widget can be toggled on/off via tray menu, just like `--preview` flag in Phase 1.
