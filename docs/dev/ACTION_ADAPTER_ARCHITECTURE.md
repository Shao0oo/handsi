# Action Adapter Architecture

This document describes the current hybrid Python/Rust action system and provides a roadmap for moving all OS-specific code to Rust for cross-platform support.

---

## Current Architecture (Hybrid)

```
┌─────────────────────────────────────────────────────────────┐
│                     Python Backend                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Gesture Recognition → Action Dispatch              │   │
│  │  (gesture detected → call adapter.move_mouse())     │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │  macos.py Adapter                                   │   │
│  │  - Screen queries (Quartz) ──────────► stays here   │   │
│  │  - Mouse position (AppKit) ──────────► stays here   │   │
│  │  - AppleScript (osascript) ──────────► stays here   │   │
│  │  - CGEvent actions ──────────────────► IPC to Rust  │   │
│  └──────────────────────┬──────────────────────────────┘   │
└─────────────────────────┼───────────────────────────────────┘
                          │ stdout (fire-and-forget JSON)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     Rust Frontend                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  input module (main.rs)                             │   │
│  │  - mouse_move, mouse_down, mouse_up                 │   │
│  │  - scroll, key_press, double_click                  │   │
│  │  - Uses core-graphics crate + FFI                   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Target Architecture (Full Rust Adapters)

```
┌─────────────────────────────────────────────────────────────┐
│                     Python Backend                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Gesture Recognition → Action Dispatch              │   │
│  │  (gesture detected → IPC: "move_mouse" with params) │   │
│  └──────────────────────┬──────────────────────────────┘   │
└─────────────────────────┼───────────────────────────────────┘
                          │ stdout (fire-and-forget JSON)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     Rust Frontend                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ActionAdapter trait                                │   │
│  │  - initialize() → bool                              │   │
│  │  - get_screen_dimensions() → (width, height)        │   │
│  │  - get_mouse_position() → (x, y)                    │   │
│  │  - move_mouse(x, y)                                 │   │
│  │  - click(button), scroll(dx, dy), key_press(...)    │   │
│  │  - switch_desktop(direction)                        │   │
│  │  - set_volume(delta)                                │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────┼──────────────────────────────┐   │
│  │                      ▼                              │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │   │
│  │  │ MacOSAdapter│ │LinuxAdapter │ │WinAdapter   │   │   │
│  │  │ (macos.rs)  │ │ (linux.rs)  │ │(windows.rs) │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## What Needs to Move to Rust

### Already in Rust (main.rs input module)

| Function | Implementation | Status |
|----------|---------------|--------|
| `mouse_move(x, y)` | `CGEvent::new_mouse_event` | Done |
| `mouse_down(x, y, button)` | `CGEvent::new_mouse_event` | Done |
| `mouse_up(x, y, button)` | `CGEvent::new_mouse_event` | Done |
| `mouse_click(x, y, button)` | down + up | Done |
| `mouse_double_click(x, y, button)` | click count field | Done |
| `scroll(dx, dy)` | `CGEventCreateScrollWheelEvent` (FFI) | Done |
| `key_press(key_code, modifiers)` | `CGEvent::new_keyboard_event` | Done |

### Still in Python (macos.py) - To Port

| Function | Current Implementation | Rust Equivalent |
|----------|----------------------|-----------------|
| `get_screen_dimensions()` | `CGDisplayBounds`, `CGGetActiveDisplayList` | `core-graphics` crate |
| `get_mouse_position()` | `NSEvent.mouseLocation()` | `core-graphics` or `objc` crate |
| `switch_desktop(direction)` | `osascript` subprocess | `std::process::Command` |
| `set_volume(delta)` | `osascript` subprocess | `std::process::Command` |
| Coordinate conversion | Python math | Rust math |

---

## Rust Implementation Plan

### File Structure

```
src-tauri/src/
├── main.rs              # Tauri app, IPC handling
├── input.rs             # Current CGEvent code (move here from main.rs)
└── adapters/
    ├── mod.rs           # ActionAdapter trait + factory
    ├── macos.rs         # macOS implementation
    ├── linux.rs         # Linux implementation (future)
    └── windows.rs       # Windows implementation (future)
```

### ActionAdapter Trait (Rust)

```rust
// src-tauri/src/adapters/mod.rs

pub trait ActionAdapter: Send + Sync {
    /// Initialize adapter, get screen dimensions
    fn initialize(&mut self) -> Result<(), String>;

    /// Get combined screen dimensions (multi-monitor)
    fn get_screen_dimensions(&self) -> (u32, u32, i32, i32); // width, height, x_offset, y_offset

    /// Get current mouse position in pixels
    fn get_mouse_position(&self) -> (f64, f64);

    /// Move mouse to absolute pixel position
    fn move_mouse(&self, x: f64, y: f64) -> Result<(), String>;

    /// Mouse button down
    fn mouse_down(&self, x: f64, y: f64, button: u8) -> Result<(), String>;

    /// Mouse button up
    fn mouse_up(&self, x: f64, y: f64, button: u8) -> Result<(), String>;

    /// Single click
    fn click(&self, x: f64, y: f64, button: u8) -> Result<(), String>;

    /// Double click
    fn double_click(&self, x: f64, y: f64, button: u8) -> Result<(), String>;

    /// Scroll wheel
    fn scroll(&self, dx: i32, dy: i32) -> Result<(), String>;

    /// Keyboard shortcut
    fn key_press(&self, key_code: u16, modifiers: u64) -> Result<(), String>;

    /// Switch virtual desktop
    fn switch_desktop(&self, direction: &str) -> Result<(), String>;

    /// Adjust system volume
    fn set_volume(&self, delta: i32) -> Result<(), String>;
}

/// Create adapter for current platform
pub fn create_adapter() -> Box<dyn ActionAdapter> {
    #[cfg(target_os = "macos")]
    return Box::new(macos::MacOSAdapter::new());

    #[cfg(target_os = "linux")]
    return Box::new(linux::LinuxAdapter::new());

    #[cfg(target_os = "windows")]
    return Box::new(windows::WindowsAdapter::new());
}
```

### macOS Adapter (Rust)

```rust
// src-tauri/src/adapters/macos.rs

use core_graphics::display::{CGDisplay, CGMainDisplayID};
use core_graphics::event::*;
use core_graphics::geometry::CGPoint;
use std::process::Command;

pub struct MacOSAdapter {
    screen_width: u32,
    screen_height: u32,
    screen_x_offset: i32,
    screen_y_offset: i32,
    main_display_height: u32,
    held_button: Option<u8>,
}

impl MacOSAdapter {
    pub fn new() -> Self {
        Self {
            screen_width: 0,
            screen_height: 0,
            screen_x_offset: 0,
            screen_y_offset: 0,
            main_display_height: 0,
            held_button: None,
        }
    }
}

impl ActionAdapter for MacOSAdapter {
    fn initialize(&mut self) -> Result<(), String> {
        // Get display info using core-graphics
        // Similar logic to Python's CGGetActiveDisplayList
        todo!("Implement screen dimension queries")
    }

    fn switch_desktop(&self, direction: &str) -> Result<(), String> {
        let key_code = match direction {
            "left" | "prev" => 123,  // Left arrow
            "right" | "next" => 124, // Right arrow
            "up" => 126,             // Up arrow (Mission Control)
            "down" => 125,           // Down arrow (App Windows)
            _ => return Err(format!("Invalid direction: {}", direction)),
        };

        let script = format!(
            r#"tell application "System Events" to key code {} using control down"#,
            key_code
        );

        Command::new("osascript")
            .args(["-e", &script])
            .output()
            .map_err(|e| e.to_string())?;

        Ok(())
    }

    fn set_volume(&self, delta: i32) -> Result<(), String> {
        // Get current volume
        let output = Command::new("osascript")
            .args(["-e", "output volume of (get volume settings)"])
            .output()
            .map_err(|e| e.to_string())?;

        let current: i32 = String::from_utf8_lossy(&output.stdout)
            .trim()
            .parse()
            .unwrap_or(50);

        let new_volume = (current + delta).clamp(0, 100);

        Command::new("osascript")
            .args(["-e", &format!("set volume output volume {}", new_volume)])
            .output()
            .map_err(|e| e.to_string())?;

        Ok(())
    }

    // ... other methods use existing input module code
}
```

### Linux Adapter (Future)

```rust
// src-tauri/src/adapters/linux.rs

// Dependencies: x11, wayland-client, or enigo crate
//
// Key differences from macOS:
// - X11: Use XTest extension for input simulation
// - Wayland: Use wlr-virtual-pointer protocol (more restricted)
// - Desktop switch: wmctrl or xdotool
// - Volume: pactl (PulseAudio) or amixer (ALSA)

pub struct LinuxAdapter {
    // X11 display connection or Wayland handle
}

impl ActionAdapter for LinuxAdapter {
    fn switch_desktop(&self, direction: &str) -> Result<(), String> {
        // Option 1: wmctrl
        // wmctrl -s <desktop_number>

        // Option 2: xdotool
        // xdotool key ctrl+Left/Right

        todo!()
    }

    fn set_volume(&self, delta: i32) -> Result<(), String> {
        // PulseAudio: pactl set-sink-volume @DEFAULT_SINK@ +5%
        // ALSA: amixer set Master 5%+
        todo!()
    }
}
```

### Windows Adapter (Future)

```rust
// src-tauri/src/adapters/windows.rs

// Dependencies: windows crate (official Microsoft bindings)
//
// Key APIs:
// - Input: SendInput() for mouse/keyboard
// - Screen: GetSystemMetrics(), EnumDisplayMonitors()
// - Desktop switch: IVirtualDesktopManager COM interface
// - Volume: IAudioEndpointVolume COM interface

pub struct WindowsAdapter {
    // Windows-specific state
}

impl ActionAdapter for WindowsAdapter {
    fn move_mouse(&self, x: f64, y: f64) -> Result<(), String> {
        // Use windows::Win32::UI::Input::KeyboardAndMouse::SendInput
        todo!()
    }

    fn switch_desktop(&self, direction: &str) -> Result<(), String> {
        // Windows 10/11 virtual desktops via COM
        // Or simulate Win+Ctrl+Left/Right
        todo!()
    }
}
```

---

## Migration Steps

### Phase 1: Refactor (Current State)
- [x] CGEvent actions moved to Rust
- [x] Fire-and-forget IPC working
- [ ] Extract input code to `input.rs` module

### Phase 2: Full macOS in Rust
- [ ] Create `adapters/` directory structure
- [ ] Define `ActionAdapter` trait
- [ ] Move screen dimension queries to Rust
- [ ] Move mouse position queries to Rust
- [ ] Move AppleScript calls to Rust
- [ ] Simplify Python macos.py to thin IPC wrapper

### Phase 3: Linux Support
- [ ] Add `x11` or `enigo` dependency
- [ ] Implement `LinuxAdapter`
- [ ] Test on Ubuntu/Fedora
- [ ] Handle Wayland (may need different approach)

### Phase 4: Windows Support
- [ ] Add `windows` crate dependency
- [ ] Implement `WindowsAdapter`
- [ ] Test on Windows 10/11
- [ ] Handle Windows-specific permissions (UAC)

---

## IPC Protocol (Python → Rust)

The IPC protocol is already designed to be OS-agnostic. Python sends action requests, Rust executes them.

### Action Messages (fire-and-forget)

```json
{"type": "action", "action": "mouse_move", "x": 500.0, "y": 300.0}
{"type": "action", "action": "mouse_down", "x": 500.0, "y": 300.0, "button": 0}
{"type": "action", "action": "mouse_up", "x": 500.0, "y": 300.0, "button": 0}
{"type": "action", "action": "click", "x": 500.0, "y": 300.0, "button": 0}
{"type": "action", "action": "double_click", "x": 500.0, "y": 300.0, "button": 0}
{"type": "action", "action": "scroll", "dx": 0, "dy": -10}
{"type": "action", "action": "key_press", "key_code": 8, "modifiers": 1048576}
{"type": "action", "action": "switch_desktop", "direction": "left"}
{"type": "action", "action": "set_volume", "delta": 5}
```

### Future: Query Messages (request-response)

For screen dimensions and mouse position, Python could query Rust:

```json
// Request
{"type": "query", "query": "screen_dimensions", "request_id": "123"}

// Response
{"type": "query_response", "request_id": "123", "data": {"width": 2560, "height": 1440, "x_offset": 0, "y_offset": 0}}
```

---

## Dependencies by Platform

### macOS (current)
```toml
[target.'cfg(target_os = "macos")'.dependencies]
core-graphics = "0.24"
# cocoa = "0.25"  # If needed for NSEvent
```

### Linux (future)
```toml
[target.'cfg(target_os = "linux")'.dependencies]
x11 = "2.21"           # X11 bindings
# Or use enigo which abstracts X11/Wayland
enigo = "0.1"
```

### Windows (future)
```toml
[target.'cfg(target_os = "windows")'.dependencies]
windows = { version = "0.52", features = [
    "Win32_UI_Input_KeyboardAndMouse",
    "Win32_Graphics_Gdi",
    "Win32_System_Com",
]}
```

---

## Notes

1. **Permission Handling**: Each platform has different permission models
   - macOS: TCC (Accessibility in System Settings)
   - Linux: Usually no special permissions needed (X11), Wayland is more locked down
   - Windows: May need admin for some operations

2. **Coordinate Systems**: Each OS has different coordinate conventions
   - macOS: Origin at bottom-left (Cocoa) or top-left (Quartz)
   - Linux/Windows: Origin at top-left

3. **Multi-Monitor**: All platforms need to handle multiple displays
   - Combined bounding box approach works universally

4. **Key Codes**: Different per platform
   - macOS: CGKeyCode values
   - Linux: X11 keysyms or evdev codes
   - Windows: Virtual key codes

---

## References

- [core-graphics crate](https://docs.rs/core-graphics/latest/core_graphics/)
- [x11 crate](https://docs.rs/x11/latest/x11/)
- [windows crate](https://docs.rs/windows/latest/windows/)
- [enigo crate](https://docs.rs/enigo/latest/enigo/) (cross-platform input)
- [Tauri cross-platform guide](https://tauri.app/v1/guides/building/cross-platform)
