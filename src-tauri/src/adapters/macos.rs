// ============================================================================
// macOS Action Adapter - CGEvent + AppleScript based implementation
// ============================================================================

use super::ActionAdapter;
use core_graphics::display::CGDirectDisplayID;
use core_graphics::event::{
    CGEvent, CGEventTapLocation, CGEventType, CGMouseButton, CGEventFlags,
};
use core_graphics::event_source::{CGEventSource, CGEventSourceStateID};
use core_graphics::geometry::CGPoint;
use std::process::Command;
use std::sync::Mutex;

// FFI bindings for CGEvent functions (not fully exposed in core-graphics crate)
#[link(name = "CoreGraphics", kind = "framework")]
extern "C" {
    fn CGEventCreateScrollWheelEvent(
        source: *const std::ffi::c_void,
        units: u32,
        wheel_count: u32,
        wheel1: i32,
        wheel2: i32,
        wheel3: i32,
    ) -> *mut std::ffi::c_void;

    fn CGEventCreate(source: *const std::ffi::c_void) -> *mut std::ffi::c_void;
    fn CGEventGetLocation(event: *const std::ffi::c_void) -> CGPoint;
    fn CGEventSetIntegerValueField(event: *mut std::ffi::c_void, field: u32, value: i64);
}

#[link(name = "CoreFoundation", kind = "framework")]
extern "C" {
    fn CFRelease(cf: *mut std::ffi::c_void);
}

// Scroll event unit: pixel-based scrolling
const K_CG_SCROLL_EVENT_UNIT_PIXEL: u32 = 0;
// Scroll wheel event field for horizontal axis
const K_CG_SCROLL_WHEEL_EVENT_DELTA_AXIS_2: u32 = 12;

/// Current held button for drag events (None = no button held)
static HELD_BUTTON: Mutex<Option<u8>> = Mutex::new(None);

/// macOS adapter using CGEvent for input control and AppleScript for system actions
pub struct MacOSAdapter {
    initialized: bool,
    // Screen dimensions for multi-monitor support
    screen_width: f64,
    screen_height: f64,
    screen_x_offset: f64,
    screen_y_offset: f64,
    // Cached system volume (0-100) to avoid querying on every adjustment
    cached_volume: Mutex<Option<i32>>,
    // Double-click time threshold (seconds) for proper click timing
    double_click_threshold: f64,
    // Tracked cursor position for gesture control (avoids repeated OS queries)
    // Updated by reset_cursor_tracking() at gesture start, then accumulated by relative moves
    tracked_cursor_x: Mutex<f64>,
    tracked_cursor_y: Mutex<f64>,
}

impl MacOSAdapter {
    pub fn new() -> Self {
        MacOSAdapter {
            initialized: false,
            screen_width: 1920.0,
            screen_height: 1080.0,
            screen_x_offset: 0.0,
            screen_y_offset: 0.0,
            cached_volume: Mutex::new(None),
            double_click_threshold: 0.5,  // Default 500ms (matching Python default)
            tracked_cursor_x: Mutex::new(0.5),  // Center of screen
            tracked_cursor_y: Mutex::new(0.5),
        }
    }

    /// Query screen dimensions for multi-monitor support
    fn query_screen_dimensions(&mut self) -> Result<(), String> {
        unsafe {
            // Get active displays (max 16 displays)
            let mut display_count: u32 = 0;
            let mut displays: [CGDirectDisplayID; 16] = [0; 16];

            let err = core_graphics::display::CGGetActiveDisplayList(
                16,
                displays.as_mut_ptr(),
                &mut display_count
            );

            if err != 0 || display_count == 0 {
                return Err("No active displays found".to_string());
            }

            // Calculate combined bounding box for all displays
            let mut min_x = f64::MAX;
            let mut min_y = f64::MAX;
            let mut max_x = f64::MIN;
            let mut max_y = f64::MIN;

            for i in 0..display_count as usize {
                let bounds = core_graphics::display::CGDisplayBounds(displays[i]);
                let display_min_x = bounds.origin.x;
                let display_min_y = bounds.origin.y;
                let display_max_x = display_min_x + bounds.size.width;
                let display_max_y = display_min_y + bounds.size.height;

                min_x = min_x.min(display_min_x);
                min_y = min_y.min(display_min_y);
                max_x = max_x.max(display_max_x);
                max_y = max_y.max(display_max_y);
            }

            // Store combined screen dimensions
            self.screen_x_offset = min_x;
            self.screen_y_offset = min_y;
            self.screen_width = max_x - min_x;
            self.screen_height = max_y - min_y;

            eprintln!("[Rust] Screen dimensions: {}x{} (offset: {}, {})",
                     self.screen_width, self.screen_height,
                     self.screen_x_offset, self.screen_y_offset);

            Ok(())
        }
    }

    /// Convert normalized coordinates [0, 1] to pixel coordinates
    fn normalized_to_pixels(&self, x_norm: f64, y_norm: f64) -> (f64, f64) {
        // Convert and truncate to match Python's int() behavior
        let pixel_x = (x_norm * self.screen_width).floor() + self.screen_x_offset;
        let pixel_y = (y_norm * self.screen_height).floor() + self.screen_y_offset;
        (pixel_x, pixel_y)
    }

    /// Execute AppleScript and return stdout (with 1 second timeout)
    fn run_applescript(&self, script: &str) -> Result<String, String> {
        use wait_timeout::ChildExt;
        use std::time::Duration;

        let mut child = Command::new("osascript")
            .args(&["-e", script])
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to spawn osascript: {}", e))?;

        // Wait with 1 second timeout (matching Python implementation)
        let timeout = Duration::from_secs(1);
        match child.wait_timeout(timeout)
            .map_err(|e| format!("Failed to wait for osascript: {}", e))? {
            Some(status) => {
                // Process completed within timeout
                let output = child.wait_with_output()
                    .map_err(|e| format!("Failed to read osascript output: {}", e))?;

                if status.success() {
                    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
                } else {
                    let error = String::from_utf8_lossy(&output.stderr).trim().to_string();
                    Err(format!("AppleScript error: {}", error))
                }
            },
            None => {
                // Timeout reached - kill the process
                child.kill().ok();
                child.wait().ok();
                Err("AppleScript execution timed out (1 second)".to_string())
            }
        }
    }
}

impl ActionAdapter for MacOSAdapter {
    fn initialize(&mut self) -> Result<(), String> {
        // Query screen dimensions for multi-monitor support
        self.query_screen_dimensions()?;

        // Permissions are inherited from parent app (checked at startup)
        self.initialized = true;
        eprintln!("[Rust] MacOSAdapter initialized successfully");
        Ok(())
    }

    fn mouse_move(&self, x: f64, y: f64) -> Result<(), String> {
        // Clamp coordinates to screen bounds (matching Python behavior)
        let clamped_x = x.max(self.screen_x_offset)
            .min(self.screen_x_offset + self.screen_width - 1.0);
        let clamped_y = y.max(self.screen_y_offset)
            .min(self.screen_y_offset + self.screen_height - 1.0);

        let source = CGEventSource::new(CGEventSourceStateID::HIDSystemState)
            .map_err(|_| "Failed to create event source")?;

        // Check if a button is held for drag events
        let held = HELD_BUTTON.lock().unwrap();
        let (event_type, button) = match *held {
            Some(0) => (CGEventType::LeftMouseDragged, CGMouseButton::Left),
            Some(1) => (CGEventType::RightMouseDragged, CGMouseButton::Right),
            Some(2) => (CGEventType::OtherMouseDragged, CGMouseButton::Center),
            _ => (CGEventType::MouseMoved, CGMouseButton::Left),
        };
        drop(held);

        let event = CGEvent::new_mouse_event(
            source,
            event_type,
            CGPoint::new(clamped_x, clamped_y),
            button,
        ).map_err(|_| "Failed to create mouse event")?;

        event.post(CGEventTapLocation::HID);
        Ok(())
    }

    fn mouse_move_normalized(&self, x_norm: f64, y_norm: f64) -> Result<(), String> {
        // Convert normalized [0, 1] to pixel coordinates
        let (pixel_x, pixel_y) = self.normalized_to_pixels(x_norm, y_norm);
        // Use regular mouse_move with pixel coordinates
        self.mouse_move(pixel_x, pixel_y)
    }

    fn mouse_down(&self, x: f64, y: f64, button: u8) -> Result<(), String> {
        let source = CGEventSource::new(CGEventSourceStateID::HIDSystemState)
            .map_err(|_| "Failed to create event source")?;

        let (event_type, cg_button) = match button {
            0 => (CGEventType::LeftMouseDown, CGMouseButton::Left),
            1 => (CGEventType::RightMouseDown, CGMouseButton::Right),
            2 => (CGEventType::OtherMouseDown, CGMouseButton::Center),
            _ => return Err(format!("Invalid button: {}", button)),
        };

        let event = CGEvent::new_mouse_event(
            source,
            event_type,
            CGPoint::new(x, y),
            cg_button,
        ).map_err(|_| "Failed to create mouse event")?;

        event.post(CGEventTapLocation::HID);

        // Track held button for drag events
        *HELD_BUTTON.lock().unwrap() = Some(button);

        Ok(())
    }

    fn mouse_up(&self, x: f64, y: f64, button: u8) -> Result<(), String> {
        let source = CGEventSource::new(CGEventSourceStateID::HIDSystemState)
            .map_err(|_| "Failed to create event source")?;

        let (event_type, cg_button) = match button {
            0 => (CGEventType::LeftMouseUp, CGMouseButton::Left),
            1 => (CGEventType::RightMouseUp, CGMouseButton::Right),
            2 => (CGEventType::OtherMouseUp, CGMouseButton::Center),
            _ => return Err(format!("Invalid button: {}", button)),
        };

        let event = CGEvent::new_mouse_event(
            source,
            event_type,
            CGPoint::new(x, y),
            cg_button,
        ).map_err(|_| "Failed to create mouse event")?;

        event.post(CGEventTapLocation::HID);

        // Clear held button
        *HELD_BUTTON.lock().unwrap() = None;

        Ok(())
    }

    fn mouse_click(&self, x: f64, y: f64, button: u8) -> Result<(), String> {
        self.mouse_down(x, y, button)?;
        self.mouse_up(x, y, button)
    }

    fn mouse_double_click(&self, _x: f64, _y: f64, button: u8) -> Result<(), String> {
        // Get current mouse position (matching Python behavior - ignores provided x, y)
        let point = unsafe {
            extern "C" {
                fn CGEventCreate(source: *const std::ffi::c_void) -> *mut std::ffi::c_void;
                fn CGEventGetLocation(event: *const std::ffi::c_void) -> CGPoint;
            }
            let event = CGEventCreate(std::ptr::null());
            if event.is_null() {
                return Err("Failed to query mouse position".to_string());
            }
            let pos = CGEventGetLocation(event);
            CFRelease(event);
            pos
        };

        let source = CGEventSource::new(CGEventSourceStateID::HIDSystemState)
            .map_err(|_| "Failed to create event source")?;

        let (down_type, up_type, cg_button) = match button {
            0 => (CGEventType::LeftMouseDown, CGEventType::LeftMouseUp, CGMouseButton::Left),
            1 => (CGEventType::RightMouseDown, CGEventType::RightMouseUp, CGMouseButton::Right),
            2 => (CGEventType::OtherMouseDown, CGEventType::OtherMouseUp, CGMouseButton::Center),
            _ => return Err(format!("Invalid button: {}", button)),
        };

        // First click (clickCount = 1)
        let down1 = CGEvent::new_mouse_event(source.clone(), down_type, point, cg_button)
            .map_err(|_| "Failed to create mouse event")?;
        down1.set_integer_value_field(core_graphics::event::EventField::MOUSE_EVENT_CLICK_STATE, 1);
        down1.post(CGEventTapLocation::HID);

        let up1 = CGEvent::new_mouse_event(source.clone(), up_type, point, cg_button)
            .map_err(|_| "Failed to create mouse event")?;
        up1.set_integer_value_field(core_graphics::event::EventField::MOUSE_EVENT_CLICK_STATE, 1);
        up1.post(CGEventTapLocation::HID);

        // Delay between clicks (25% of system double-click threshold, matching Python)
        let delay = std::time::Duration::from_secs_f64(self.double_click_threshold * 0.25);
        std::thread::sleep(delay);

        // Second click (clickCount = 2)
        let down2 = CGEvent::new_mouse_event(source.clone(), down_type, point, cg_button)
            .map_err(|_| "Failed to create mouse event")?;
        down2.set_integer_value_field(core_graphics::event::EventField::MOUSE_EVENT_CLICK_STATE, 2);
        down2.post(CGEventTapLocation::HID);

        let up2 = CGEvent::new_mouse_event(source, up_type, point, cg_button)
            .map_err(|_| "Failed to create mouse event")?;
        up2.set_integer_value_field(core_graphics::event::EventField::MOUSE_EVENT_CLICK_STATE, 2);
        up2.post(CGEventTapLocation::HID);

        Ok(())
    }

    fn mouse_down_normalized(&self, _x_norm: f64, _y_norm: f64, button: u8) -> Result<(), String> {
        // Query actual OS position for accurate clicks (ignore provided coordinates)
        let (actual_x, actual_y) = self.get_mouse_position_normalized()?;
        let (pixel_x, pixel_y) = self.normalized_to_pixels(actual_x, actual_y);
        self.mouse_down(pixel_x, pixel_y, button)
    }

    fn mouse_up_normalized(&self, _x_norm: f64, _y_norm: f64, button: u8) -> Result<(), String> {
        // Query actual OS position for accurate clicks (ignore provided coordinates)
        let (actual_x, actual_y) = self.get_mouse_position_normalized()?;
        let (pixel_x, pixel_y) = self.normalized_to_pixels(actual_x, actual_y);
        self.mouse_up(pixel_x, pixel_y, button)
    }

    fn mouse_click_normalized(&self, _x_norm: f64, _y_norm: f64, button: u8) -> Result<(), String> {
        // Query actual OS position for accurate clicks (ignore provided coordinates)
        let (actual_x, actual_y) = self.get_mouse_position_normalized()?;
        let (pixel_x, pixel_y) = self.normalized_to_pixels(actual_x, actual_y);
        self.mouse_click(pixel_x, pixel_y, button)
    }

    fn mouse_double_click_normalized(&self, _x_norm: f64, _y_norm: f64, button: u8) -> Result<(), String> {
        // Query actual OS position for accurate clicks (ignore provided coordinates)
        let (actual_x, actual_y) = self.get_mouse_position_normalized()?;
        let (pixel_x, pixel_y) = self.normalized_to_pixels(actual_x, actual_y);
        self.mouse_double_click(pixel_x, pixel_y, button)
    }

    fn scroll(&self, dx: i32, dy: i32) -> Result<(), String> {
        // Convert pixels to lines (10 pixels = 1 line)
        let mut scroll_lines_y = dy / 10;
        let mut scroll_lines_x = dx / 10;

        // Handle small movements (< 10 pixels) - ensure they still register
        if scroll_lines_y == 0 && dy != 0 {
            scroll_lines_y = if dy > 0 { 1 } else { -1 };
        }
        if scroll_lines_x == 0 && dx != 0 {
            scroll_lines_x = if dx > 0 { 1 } else { -1 };
        }

        // Invert for natural scrolling (macOS convention)
        let scroll_dy = -scroll_lines_y;
        let scroll_dx = -scroll_lines_x;

        unsafe {
            // Create scroll event with vertical axis
            let event_ref = CGEventCreateScrollWheelEvent(
                std::ptr::null(),
                K_CG_SCROLL_EVENT_UNIT_PIXEL,
                1,
                scroll_dy,
                0,
                0,
            );

            if event_ref.is_null() {
                return Err("Failed to create scroll event".to_string());
            }

            // Add horizontal axis if needed (bypasses variadic FFI issue)
            if scroll_dx != 0 {
                CGEventSetIntegerValueField(
                    event_ref,
                    K_CG_SCROLL_WHEEL_EVENT_DELTA_AXIS_2,
                    scroll_dx as i64,
                );
            }

            // Post the event
            extern "C" {
                fn CGEventPost(tap: u32, event: *mut std::ffi::c_void);
            }
            const K_CG_HID_EVENT_TAP: u32 = 0;
            CGEventPost(K_CG_HID_EVENT_TAP, event_ref);

            CFRelease(event_ref);
        }

        Ok(())
    }

    fn get_mouse_position_normalized(&self) -> Result<(f64, f64), String> {
        // Query actual cursor position from OS (not cached)
        let point = unsafe {
            let event = CGEventCreate(std::ptr::null());
            if event.is_null() {
                return Err("Failed to query mouse position".to_string());
            }
            let pos = CGEventGetLocation(event);
            CFRelease(event);
            pos
        };

        // Normalize to [0, 1] range relative to screen bounds
        let normalized_x = (point.x - self.screen_x_offset) / self.screen_width;
        let normalized_y = (point.y - self.screen_y_offset) / self.screen_height;

        // Clamp to [0, 1]
        let clamped_x = normalized_x.max(0.0).min(1.0);
        let clamped_y = normalized_y.max(0.0).min(1.0);

        Ok((clamped_x, clamped_y))
    }

    fn mouse_move_relative_normalized(&self, dx: f64, dy: f64) -> Result<(), String> {
        // Get tracked position (NOT querying OS - avoids jitter)
        let mut tracked_x = self.tracked_cursor_x.lock().unwrap();
        let mut tracked_y = self.tracked_cursor_y.lock().unwrap();

        // Apply delta and clamp to screen bounds
        let new_x = (*tracked_x + dx).clamp(0.0, 1.0);
        let new_y = (*tracked_y + dy).clamp(0.0, 1.0);

        // Update tracked position
        *tracked_x = new_x;
        *tracked_y = new_y;

        // Move cursor to new position
        self.mouse_move_normalized(new_x, new_y)
    }

    fn reset_cursor_tracking(&self) -> Result<(), String> {
        // Query actual OS position
        let (actual_x, actual_y) = self.get_mouse_position_normalized()?;

        // Update tracked position to actual
        *self.tracked_cursor_x.lock().unwrap() = actual_x;
        *self.tracked_cursor_y.lock().unwrap() = actual_y;

        eprintln!("[Rust] Cursor tracking reset to ({:.3}, {:.3})", actual_x, actual_y);
        Ok(())
    }

    fn key_press(&self, key_code: u16, modifiers: u64) -> Result<(), String> {
        let source = CGEventSource::new(CGEventSourceStateID::HIDSystemState)
            .map_err(|_| "Failed to create event source")?;

        // Create key down event
        let key_down = CGEvent::new_keyboard_event(source.clone(), key_code, true)
            .map_err(|_| "Failed to create key down event")?;

        // Set modifier flags
        let flags = CGEventFlags::from_bits_truncate(modifiers);
        key_down.set_flags(flags);
        key_down.post(CGEventTapLocation::HID);

        // Create key up event
        let key_up = CGEvent::new_keyboard_event(source.clone(), key_code, false)
            .map_err(|_| "Failed to create key up event")?;
        key_up.post(CGEventTapLocation::HID);

        // Post flags changed event with empty flags to release modifiers (Command, Control, etc.)
        if modifiers != 0 {
            let flags_event = CGEvent::new_keyboard_event(source, 0, true)
                .map_err(|_| "Failed to create flags event")?;
            flags_event.set_type(CGEventType::FlagsChanged);
            flags_event.set_flags(CGEventFlags::empty());
            flags_event.post(CGEventTapLocation::HID);
        }


        Ok(())
    }

    fn switch_desktop(&self, direction: &str) -> Result<(), String> {
        // Map direction to key code (arrow keys)
        let key_code = match direction {
            "left" | "prev" => 123,  // Left arrow
            "right" | "next" => 124, // Right arrow
            "up" => 126,             // Up arrow (for Expose/Mission Control)
            "down" => 125,           // Down arrow
            _ => return Err(format!("Invalid direction: {}", direction)),
        };

        // Use AppleScript with System Events to send Control+Arrow
        // This is the only reliable way to trigger Mission Control desktop switching
        let script = format!(
            r#"tell application "System Events" to key code {} using control down"#,
            key_code
        );

        self.run_applescript(&script)?;
        eprintln!("[Rust] Desktop switch executed: Control+{} (key_code={})", direction, key_code);
        Ok(())
    }

    fn set_volume(&self, delta: i32) -> Result<(), String> {
        // Get current volume from cache, or query if not cached
        let mut volume_lock = self.cached_volume.lock().unwrap();
        let current = if let Some(cached) = *volume_lock {
            cached
        } else {
            // First time - query actual system volume
            let current_str = self.run_applescript("output volume of (get volume settings)")?;
            let vol = current_str.parse()
                .map_err(|_| format!("Failed to parse volume: {}", current_str))?;
            *volume_lock = Some(vol);
            vol
        };

        // Calculate new volume (clamp to 0-100)
        let new_volume = (current + delta).clamp(0, 100);

        // Set new volume
        let script = format!("set volume output volume {}", new_volume);
        self.run_applescript(&script)?;

        // Update cache
        *volume_lock = Some(new_volume);

        eprintln!("[Rust] Volume adjusted: {} -> {} (delta: {})", current, new_volume, delta);
        Ok(())
    }

    fn keyboard_shortcut(&self, shortcut: &str) -> Result<(), String> {
        // Parse shortcut string like "cmd+c", "ctrl+shift+tab"
        let parts: Vec<&str> = shortcut.split('+').collect();
        if parts.len() < 2 {
            return Err(format!("Invalid shortcut format: {}", shortcut));
        }

        // Last part is the key, everything before is modifiers
        let key_str = parts.last().unwrap().to_lowercase();
        let modifier_strs = &parts[..parts.len() - 1];

        // Combine all modifiers using bitwise OR
        let mut modifiers = 0u64;
        for modifier_str in modifier_strs {
            let modifier_flag = match modifier_str.to_lowercase().as_str() {
                "cmd" | "command" => CGEventFlags::CGEventFlagCommand.bits(),
                "ctrl" | "control" => CGEventFlags::CGEventFlagControl.bits(),
                "alt" | "option" => CGEventFlags::CGEventFlagAlternate.bits(),
                "shift" => CGEventFlags::CGEventFlagShift.bits(),
                _ => return Err(format!("Unknown modifier: {}", modifier_str)),
            };
            modifiers |= modifier_flag;  // Combine with bitwise OR
        }

        // Map key strings to macOS virtual key codes
        let key_code: u16 = match key_str.as_str() {
            "c" => 8,   // C key
            "v" => 9,   // V key
            "z" => 6,   // Z key
            "x" => 7,   // X key
            "a" => 0,   // A key
            "s" => 1,   // S key
            "f" => 3,   // F key
            "w" => 13,  // W key
            "q" => 12,  // Q key
            "t" => 17,  // T key
            "tab" => 48,
            _ => return Err(format!("Unknown key: {}", key_str)),
        };

        self.key_press(key_code, modifiers)?;
        eprintln!("[Rust] Keyboard shortcut executed: {}", shortcut);
        Ok(())
    }

    fn zoom(&self, direction: &str, _step: f64) -> Result<(), String> {
        // Use Cmd+Plus and Cmd+Minus for browser/app zoom
        let key_code = match direction {
            "in" => 24,  // Plus/Equal key
            "out" => 27, // Minus key
            _ => return Err(format!("Invalid zoom direction: {}", direction)),
        };

        // Cmd modifier
        let modifiers = CGEventFlags::CGEventFlagCommand.bits();
        self.key_press(key_code, modifiers)?;
        eprintln!("[Rust] Zoom executed: {}", direction);
        Ok(())
    }

    fn semantic_action(&self, name: &str) -> Result<(), String> {
        // Map semantic actions to macOS shortcuts (Cmd key)
        let shortcut = match name {
            "copy" => "cmd+c",
            "paste" => "cmd+v",
            "undo" => "cmd+z",
            "redo" => "cmd+shift+z",
            "cut" => "cmd+x",
            "select_all" => "cmd+a",
            _ => return Err(format!("Unknown semantic action: {}", name)),
        };
        eprintln!("[Rust] Semantic action '{}' -> shortcut '{}'", name, shortcut);
        self.keyboard_shortcut(shortcut)
    }

    fn cleanup(&mut self) {
        // Clear held button state
        *HELD_BUTTON.lock().unwrap() = None;
        // Clear volume cache
        *self.cached_volume.lock().unwrap() = None;
        self.initialized = false;
        eprintln!("[Rust] MacOSAdapter cleaned up");
    }
}

impl Drop for MacOSAdapter {
    fn drop(&mut self) {
        if self.initialized {
            self.cleanup();
        }
    }
}
