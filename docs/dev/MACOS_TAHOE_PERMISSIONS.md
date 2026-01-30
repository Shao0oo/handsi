# macOS Tahoe Permission Issues & CGEvent Migration Plan

## Problem Summary

On **macOS Tahoe (macOS 26)**, the bundled Handsi app cannot execute CGEvent-based actions (mouse, scroll, click, keyboard) due to TCC (Transparency, Consent, Control) permission issues with sidecar/child processes.

**What works:** Desktop swipe (uses AppleScript via `osascript`)
**What doesn't work:** Mouse movement, scrolling, clicking, keyboard shortcuts (use CGEventPost)

## Root Cause

### TCC Architecture

macOS has separate TCC services for input:

| TCC Service | UI Location | Purpose |
|-------------|-------------|---------|
| `kTCCServiceAccessibility` | Privacy > Accessibility | AX APIs, AppleScript UI scripting |
| `kTCCServiceListenEvent` | Privacy > Input Monitoring | CGEventTap listening |
| `kTCCServicePostEvent` | Privacy > Accessibility* | CGEventPost (synthetic input) |

*PostEvent appears under "Accessibility" in System Settings but is a **separate database entry**.

### The Sidecar Problem

Handsi has two executables:
```
Handsi.app/Contents/MacOS/
├── handsi            # Tauri/Rust frontend (has permission when added to Accessibility)
└── handsi-backend    # PyInstaller Python binary (NO permission, can't be added separately)
```

When you add "Handsi.app" to Accessibility:
- Permission is granted to `handsi` (the main executable)
- `handsi-backend` is a **separate process** and doesn't inherit permission
- macOS Tahoe **blocks adding executables inside app bundles** to Accessibility manually
- This is a [known Tauri bug](https://github.com/tauri-apps/tauri/issues/8329)

### Why Desktop Swipe Works

Desktop swipe uses:
```python
subprocess.run(['osascript', '-e', 'tell application "System Events" to key code 123 using control down'])
```

This works because:
- `osascript` is a **system binary** (already trusted)
- It uses **Automation permission** (granted to Handsi for System Events)
- It does NOT use CGEventPost

### Why Other Actions Fail

Mouse, scroll, click, keyboard use:
```python
CGEventPost(kCGHIDEventTap, event)
```

This fails because:
- `handsi-backend` calls CGEventPost
- `handsi-backend` doesn't have PostEvent/Accessibility permission
- CGEventPost **silently fails** (no error, just does nothing)

## Evidence Gathered

1. **Running from Terminal works** - Terminal has Accessibility permission, child processes inherit it
2. **`AXIsProcessTrusted()` returns False** for handsi-backend in bundled app
3. **`tccutil reset PostEvent com.handsi.desktop`** succeeds - confirming PostEvent is a separate service
4. **Code signing mentioned as solution** in Tauri issue, but ad-hoc signing doesn't work

## Current State of Code

### macos.py (Python Backend)
- Added `AXIsProcessTrustedWithOptions` check with prompt
- Prompts user to grant Accessibility permission
- But granting permission to "Handsi.app" doesn't help handsi-backend

### main.rs (Rust Frontend)
- Added `check_accessibility_permission()` function
- Uses AppleScript to check/prompt for Accessibility on startup
- Adds "Handsi" to Accessibility list, but doesn't solve the child process issue

## Proposed Solution: Move CGEvent to Rust Frontend

### Concept

Move CGEventPost calls from Python backend to Rust frontend, since the Rust process **does** have permission.

```
Current (broken):
Python Backend → CGEventPost() ❌ (no permission)

Proposed (should work):
Python Backend → IPC → Rust Frontend → CGEventPost() ✅ (has permission)
```

### Implementation Plan

#### 1. Add core-graphics dependency to Cargo.toml

```toml
[dependencies]
core-graphics = "0.23"
```

#### 2. Create input module in Rust (main.rs or input.rs)

```rust
#[cfg(target_os = "macos")]
mod input {
    use core_graphics::event::{CGEvent, CGEventTapLocation, CGMouseButton, CGEventType};
    use core_graphics::event_source::{CGEventSource, CGEventSourceStateID};
    use core_graphics::geometry::CGPoint;

    pub fn mouse_move(x: f64, y: f64) -> Result<(), String> {
        let source = CGEventSource::new(CGEventSourceStateID::HIDSystemState)
            .map_err(|_| "Failed to create event source")?;

        let event = CGEvent::new_mouse_event(
            source,
            CGEventType::MouseMoved,
            CGPoint::new(x, y),
            CGMouseButton::Left,
        ).map_err(|_| "Failed to create mouse event")?;

        event.post(CGEventTapLocation::HID);
        Ok(())
    }

    pub fn mouse_click(x: f64, y: f64, button: &str) -> Result<(), String> {
        // Similar implementation for click
    }

    pub fn scroll(dx: i32, dy: i32) -> Result<(), String> {
        // Scroll implementation
    }

    pub fn key_press(key_code: u16, modifiers: u64) -> Result<(), String> {
        // Keyboard implementation
    }
}
```

#### 3. Add Tauri commands for input actions

```rust
#[tauri::command]
fn execute_mouse_move(x: f64, y: f64) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    return input::mouse_move(x, y);
    #[cfg(not(target_os = "macos"))]
    Err("Not implemented on this platform".to_string())
}

// Similar for click, scroll, keyboard
```

#### 4. Set up reverse IPC (Python → Rust)

Current IPC is one-way (Rust sends commands to Python via stdin, Python responds via stdout).

Options for Python to trigger Rust actions:
1. **Separate channel**: Python writes to a pipe/socket that Rust reads
2. **Action queue**: Python writes actions to stdout with special prefix, Rust processes them
3. **Shared memory**: Use mmap for low-latency communication

Recommended: **Option 2 (Action queue)** - modify existing IPC protocol:

**Important:** Current IPC is synchronous request-response (Rust waits for Python's response). For 60Hz mouse moves, we need **fire-and-forget** from Python's side.

**Python side (fire-and-forget):**
```python
# Python sends action request via stdout (no response expected):
print(json.dumps({"type": "action", "action": "mouse_move", "x": 500, "y": 300}), flush=True)
# Does NOT wait for response - continues immediately
```

**Rust side (separate reader thread):**
```rust
// In a separate thread, continuously read Python's stdout
// and process actions without blocking main IPC
std::thread::spawn(move || {
    for line in reader.lines() {
        if let Ok(line) = line {
            if let Ok(msg) = serde_json::from_str::<serde_json::Value>(&line) {
                if msg.get("type") == Some(&json!("action")) {
                    // Execute CGEvent immediately
                    match msg["action"].as_str() {
                        Some("mouse_move") => {
                            let x = msg["x"].as_f64().unwrap_or(0.0);
                            let y = msg["y"].as_f64().unwrap_or(0.0);
                            input::mouse_move(x, y);
                        }
                        // ... other actions
                    }
                } else {
                    // Regular IPC response - forward to main thread
                }
            }
        }
    }
});
```

**Key design points:**
- Actions are fire-and-forget (no response, no blocking)
- Regular IPC commands still work synchronously
- Action thread processes at line speed (~0.5ms per action)
- 60Hz = 16.6ms between moves, plenty of headroom

#### 5. Modify Python macos.py adapter

Instead of calling CGEventPost directly:
```python
def move_mouse(self, x: float, y: float, ...) -> bool:
    # Instead of CGEventPost, send to frontend
    self._send_action({"action": "mouse_move", "x": pixel_x, "y": pixel_y})
    return True
```

### Files to Modify

| File | Changes |
|------|---------|
| `src-tauri/Cargo.toml` | Add `core-graphics = "0.23"` |
| `src-tauri/src/main.rs` | Add input module, Tauri commands, action processing |
| `src/handsi/actions/adapters/macos.py` | Replace CGEventPost calls with IPC to frontend |
| `src/handsi/ui/ipc_server.py` | Add action sending capability |

### Considerations

1. **Latency**: Extra IPC round-trip adds ~1-5ms latency (probably acceptable)
2. **Complexity**: Significant refactoring required
3. **Testing**: Need to test all gesture→action flows
4. **Platform-specific**: Only affects macOS, Linux adapter unchanged

## Alternative Solutions

### 1. Code Signing ($99/year)
- Proper Apple Developer certificate
- Sign both executables with same team ID
- Most reliable long-term solution

### 2. AppleScript for All Actions
- Convert mouse/scroll/click to AppleScript
- Slower and less precise
- Would use same permission path as swipe

### 3. Document Restart Workaround
- Sometimes system restart grants permission
- Not reliable, poor UX

## Useful Commands

```bash
# Reset TCC permissions
tccutil reset Accessibility com.handsi.desktop
tccutil reset PostEvent com.handsi.desktop
tccutil reset All com.handsi.desktop

# Check code signing
codesign -dv --verbose=4 /Applications/Handsi.app
codesign -dv --verbose=4 /Applications/Handsi.app/Contents/MacOS/handsi-backend

# Test permission from Python
conda activate handsi && PYTHONPATH=src python -c "
import objc
from Foundation import NSBundle
app_services = NSBundle.bundleWithPath_('/System/Library/Frameworks/ApplicationServices.framework')
objc.loadBundleFunctions(app_services, globals(), [('AXIsProcessTrusted', b'Z')])
print(f'AXIsProcessTrusted: {AXIsProcessTrusted()}')
"
```

## References

- [Tauri Issue #8329: Sidecar doesn't inherit accessibility rights](https://github.com/tauri-apps/tauri/issues/8329)
- [Apple Developer Forums: CGRequestPostEventAccess](https://developer.apple.com/forums/thread/724603)
- [Apple Developer Forums: AXIsProcessTrustedWithOptions](https://developer.apple.com/forums/thread/794253)
- [core-graphics Rust crate](https://docs.rs/core-graphics/latest/core_graphics/)

## Status

- [x] Identified root cause (TCC sidecar permission issue)
- [x] Confirmed with AXIsProcessTrusted checks
- [x] Added permission prompts (doesn't solve core issue)
- [ ] Implement CGEvent in Rust frontend
- [ ] Set up reverse IPC (Python → Rust)
- [ ] Test all actions work with new architecture
