// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::sync::mpsc::{channel, Receiver};
use tauri::Manager;

// ============================================================================
// macOS Input Module - CGEvent-based mouse/keyboard control
// ============================================================================
#[cfg(target_os = "macos")]
mod input {
    use core_graphics::event::{
        CGEvent, CGEventTapLocation, CGEventType, CGMouseButton,
        CGEventFlags,
    };
    use core_graphics::event_source::{CGEventSource, CGEventSourceStateID};
    use core_graphics::geometry::CGPoint;

    // FFI binding for CGEventCreateScrollWheelEvent (not exposed in core-graphics crate)
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
    }

    // Scroll event unit: pixel-based scrolling
    const K_CG_SCROLL_EVENT_UNIT_PIXEL: u32 = 0;

    /// Current held button for drag events (None = no button held)
    static HELD_BUTTON: std::sync::Mutex<Option<u8>> = std::sync::Mutex::new(None);

    /// Move mouse cursor to absolute pixel position
    pub fn mouse_move(x: f64, y: f64) -> Result<(), String> {
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
            CGPoint::new(x, y),
            button,
        ).map_err(|_| "Failed to create mouse event")?;

        event.post(CGEventTapLocation::HID);
        Ok(())
    }

    /// Press mouse button (0=left, 1=right, 2=middle)
    pub fn mouse_down(x: f64, y: f64, button: u8) -> Result<(), String> {
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

    /// Release mouse button (0=left, 1=right, 2=middle)
    pub fn mouse_up(x: f64, y: f64, button: u8) -> Result<(), String> {
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

    /// Click mouse button (down + up)
    pub fn mouse_click(x: f64, y: f64, button: u8) -> Result<(), String> {
        mouse_down(x, y, button)?;
        mouse_up(x, y, button)
    }

    /// Double-click with proper click count
    pub fn mouse_double_click(x: f64, y: f64, button: u8) -> Result<(), String> {
        let source = CGEventSource::new(CGEventSourceStateID::HIDSystemState)
            .map_err(|_| "Failed to create event source")?;

        let (down_type, up_type, cg_button) = match button {
            0 => (CGEventType::LeftMouseDown, CGEventType::LeftMouseUp, CGMouseButton::Left),
            1 => (CGEventType::RightMouseDown, CGEventType::RightMouseUp, CGMouseButton::Right),
            2 => (CGEventType::OtherMouseDown, CGEventType::OtherMouseUp, CGMouseButton::Center),
            _ => return Err(format!("Invalid button: {}", button)),
        };

        let point = CGPoint::new(x, y);

        // First click (clickCount = 1)
        let down1 = CGEvent::new_mouse_event(source.clone(), down_type, point, cg_button)
            .map_err(|_| "Failed to create mouse event")?;
        down1.set_integer_value_field(core_graphics::event::EventField::MOUSE_EVENT_CLICK_STATE, 1);
        down1.post(CGEventTapLocation::HID);

        let up1 = CGEvent::new_mouse_event(source.clone(), up_type, point, cg_button)
            .map_err(|_| "Failed to create mouse event")?;
        up1.set_integer_value_field(core_graphics::event::EventField::MOUSE_EVENT_CLICK_STATE, 1);
        up1.post(CGEventTapLocation::HID);

        // Small delay between clicks
        std::thread::sleep(std::time::Duration::from_millis(50));

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

    /// Scroll wheel event
    pub fn scroll(dx: i32, dy: i32) -> Result<(), String> {
        // Note: macOS scroll direction is inverted for "natural" scrolling
        // We invert here so positive dy = scroll down (content moves up)
        let scroll_dy = -dy;
        let scroll_dx = -dx;

        // Create scroll event using FFI
        unsafe {
            let event_ref = CGEventCreateScrollWheelEvent(
                std::ptr::null(),  // No event source
                K_CG_SCROLL_EVENT_UNIT_PIXEL,
                2,  // wheel_count (2 = both vertical and horizontal)
                scroll_dy,
                scroll_dx,
                0,  // wheel3 (unused)
            );

            if event_ref.is_null() {
                return Err("Failed to create scroll event".to_string());
            }

            // Post the event using CGEventPost FFI
            extern "C" {
                fn CGEventPost(tap: u32, event: *mut std::ffi::c_void);
            }
            const K_CG_HID_EVENT_TAP: u32 = 0;
            CGEventPost(K_CG_HID_EVENT_TAP, event_ref);

            // Release the event
            extern "C" {
                fn CFRelease(cf: *mut std::ffi::c_void);
            }
            CFRelease(event_ref);
        }

        Ok(())
    }

    /// Keyboard event (key down + key up)
    pub fn key_press(key_code: u16, modifiers: u64) -> Result<(), String> {
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
        let key_up = CGEvent::new_keyboard_event(source, key_code, false)
            .map_err(|_| "Failed to create key up event")?;
        key_up.set_flags(flags);
        key_up.post(CGEventTapLocation::HID);

        Ok(())
    }
}

// Stub module for non-macOS platforms
#[cfg(not(target_os = "macos"))]
mod input {
    pub fn mouse_move(_x: f64, _y: f64) -> Result<(), String> {
        Err("Not supported on this platform".to_string())
    }
    pub fn mouse_down(_x: f64, _y: f64, _button: u8) -> Result<(), String> {
        Err("Not supported on this platform".to_string())
    }
    pub fn mouse_up(_x: f64, _y: f64, _button: u8) -> Result<(), String> {
        Err("Not supported on this platform".to_string())
    }
    pub fn mouse_click(_x: f64, _y: f64, _button: u8) -> Result<(), String> {
        Err("Not supported on this platform".to_string())
    }
    pub fn mouse_double_click(_x: f64, _y: f64, _button: u8) -> Result<(), String> {
        Err("Not supported on this platform".to_string())
    }
    pub fn scroll(_dx: i32, _dy: i32) -> Result<(), String> {
        Err("Not supported on this platform".to_string())
    }
    pub fn key_press(_key_code: u16, _modifiers: u64) -> Result<(), String> {
        Err("Not supported on this platform".to_string())
    }
}

// ============================================================================
// Action Processing - Handle fire-and-forget actions from Python
// ============================================================================
fn process_action(msg: &serde_json::Value) {
    let action = match msg.get("action").and_then(|v| v.as_str()) {
        Some(a) => a,
        None => {
            eprintln!("[Rust] Action message missing 'action' field");
            return;
        }
    };

    let result = match action {
        "mouse_move" => {
            let x = msg.get("x").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let y = msg.get("y").and_then(|v| v.as_f64()).unwrap_or(0.0);
            input::mouse_move(x, y)
        }
        "mouse_down" => {
            let x = msg.get("x").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let y = msg.get("y").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let button = msg.get("button").and_then(|v| v.as_u64()).unwrap_or(0) as u8;
            input::mouse_down(x, y, button)
        }
        "mouse_up" => {
            let x = msg.get("x").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let y = msg.get("y").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let button = msg.get("button").and_then(|v| v.as_u64()).unwrap_or(0) as u8;
            input::mouse_up(x, y, button)
        }
        "click" => {
            let x = msg.get("x").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let y = msg.get("y").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let button = msg.get("button").and_then(|v| v.as_u64()).unwrap_or(0) as u8;
            input::mouse_click(x, y, button)
        }
        "double_click" => {
            let x = msg.get("x").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let y = msg.get("y").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let button = msg.get("button").and_then(|v| v.as_u64()).unwrap_or(0) as u8;
            input::mouse_double_click(x, y, button)
        }
        "scroll" => {
            let dx = msg.get("dx").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
            let dy = msg.get("dy").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
            input::scroll(dx, dy)
        }
        "key_press" => {
            let key_code = msg.get("key_code").and_then(|v| v.as_u64()).unwrap_or(0) as u16;
            let modifiers = msg.get("modifiers").and_then(|v| v.as_u64()).unwrap_or(0);
            input::key_press(key_code, modifiers)
        }
        _ => {
            eprintln!("[Rust] Unknown action: {}", action);
            Ok(())
        }
    };

    if let Err(e) = result {
        eprintln!("[Rust] Action '{}' failed: {}", action, e);
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct IpcCommand {
    command: String,
    args: serde_json::Value,
}

#[derive(Debug, Serialize, Deserialize)]
struct IpcResponse {
    success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    data: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    request_id: Option<String>,
}

struct PythonProcess {
    child: Option<Child>,
    stdin: Option<std::process::ChildStdin>,
    /// Channel receiver for IPC responses (actions are processed separately)
    response_receiver: Option<Receiver<String>>,
}

impl PythonProcess {
    fn new() -> Self {
        PythonProcess {
            child: None,
            stdin: None,
            response_receiver: None,
        }
    }

    fn start(&mut self, config_path: &str, app_handle: Option<&tauri::AppHandle>) -> Result<(), String> {
        if self.child.is_some() {
            return Err("Python process already running".to_string());
        }

        eprintln!("[Rust] Starting Python IPC process...");
        eprintln!("[Rust] Config path: {}", config_path);

        let mut child = if cfg!(debug_assertions) {
            // DEV MODE: Use system Python with source code
            eprintln!("[Rust] Dev mode: Using system Python");

            let current_exe = std::env::current_exe()
                .map_err(|e| format!("Failed to get current exe: {}", e))?;
            let exe_dir = current_exe.parent()
                .ok_or("Failed to get exe parent directory".to_string())?;

            // In dev mode, we're in src-tauri/target/debug/, need to go up to project root
            let project_root = exe_dir.parent()
                .and_then(|p| p.parent())
                .and_then(|p| p.parent())
                .ok_or("Failed to find project root".to_string())?;

            let src_path = project_root.join("src");
            eprintln!("[Rust] Project root: {:?}", project_root);
            eprintln!("[Rust] PYTHONPATH: {:?}", src_path);
            eprintln!("[Rust] Command: python -m handsi.main --ipc stdio --config {}", config_path);

            Command::new("python")
                .args(&["-m", "handsi.main", "--ipc", "stdio", "--config", config_path])
                .current_dir(project_root)
                .env("PYTHONPATH", &src_path)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .map_err(|e| format!("Failed to start Python process: {}", e))?
        } else {
            // PRODUCTION MODE: Use bundled sidecar
            eprintln!("[Rust] Production mode: Using bundled sidecar");

            let app_handle = app_handle.ok_or("App handle required in production mode")?;

            // Resolve paths using Tauri's resource resolver
            // Note: Tauri v2 bundles resources under Resources/ directory
            // but the actual files are in Resources/_up_/ subdirectory
            let resources_dir = app_handle.path().resource_dir()
                .map_err(|e| format!("Failed to get resource directory: {}", e))?;
            let config_resource = resources_dir.join("_up_").join("config").join("default.yaml");
            let config_str = config_resource.to_str()
                .ok_or("Config path contains invalid UTF-8")?;

            // Resolve sidecar binary path
            // Tauri strips the target triple when bundling
            // In macOS .app bundle: Handsi.app/Contents/MacOS/handsi-backend
            let current_exe = std::env::current_exe()
                .map_err(|e| format!("Failed to get current exe: {}", e))?;
            let exe_dir = current_exe.parent()
                .ok_or("Failed to get exe parent directory".to_string())?;

            let sidecar_name = "handsi-backend";
            let sidecar_path = exe_dir.join(sidecar_name);

            if !sidecar_path.exists() {
                return Err(format!("Sidecar binary not found at: {:?}", sidecar_path));
            }

            eprintln!("[Rust] Sidecar path: {:?}", sidecar_path);
            eprintln!("[Rust] Resolved config path: {}", config_str);
            eprintln!("[Rust] Command: {} --ipc stdio --config {}", sidecar_name, config_str);

            Command::new(&sidecar_path)
                .args(&["--ipc", "stdio", "--config", config_str])
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .map_err(|e| format!("Failed to start sidecar process: {}", e))?
        };

        eprintln!("[Rust] Python process spawned with PID: {}", child.id());

        // Take ownership of stdin/stdout/stderr
        self.stdin = child.stdin.take();
        let stdout = child.stdout.take()
            .ok_or("Failed to capture Python stdout".to_string())?;

        // Create channel for IPC responses (actions bypass this channel)
        let (response_tx, response_rx) = channel::<String>();
        self.response_receiver = Some(response_rx);

        // Spawn a thread to read Python's stdout
        // This thread handles both:
        // 1. Action messages (type: "action") - executed immediately via CGEvent
        // 2. IPC responses - forwarded to response channel for send_command to receive
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                if let Ok(line) = line {
                    if line.trim().is_empty() {
                        continue;
                    }

                    // Try to parse as JSON
                    match serde_json::from_str::<serde_json::Value>(&line) {
                        Ok(msg) => {
                            // Check if this is an action message
                            if msg.get("type").and_then(|v| v.as_str()) == Some("action") {
                                // Process action immediately (fire-and-forget)
                                process_action(&msg);
                            } else {
                                // Regular IPC response - forward to channel
                                if let Err(e) = response_tx.send(line) {
                                    eprintln!("[Rust] Failed to forward IPC response: {}", e);
                                    break;
                                }
                            }
                        }
                        Err(e) => {
                            eprintln!("[Rust] Failed to parse Python output as JSON: {} - line: {}", e, line);
                            // Still try to forward it in case it's a malformed response
                            if let Err(_) = response_tx.send(line) {
                                break;
                            }
                        }
                    }
                }
            }
            eprintln!("[Rust] Python stdout reader thread exiting");
        });

        // Spawn a thread to monitor stderr
        if let Some(stderr) = child.stderr.take() {
            std::thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines() {
                    if let Ok(line) = line {
                        eprintln!("[Python stderr] {}", line);
                    }
                }
            });
        }

        self.child = Some(child);
        eprintln!("[Rust] Python IPC process started successfully");

        Ok(())
    }

    fn send_command(&mut self, command: &str, args: serde_json::Value) -> Result<IpcResponse, String> {
        if self.child.is_none() {
            return Err("Python process not running".to_string());
        }

        // Generate unique request ID
        use std::time::{SystemTime, UNIX_EPOCH, Duration};
        let request_id = format!("{}-{}",
            SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_millis(),
            command
        );

        eprintln!("[Rust] Sending command to Python: {} (request_id: {})", command, request_id);

        let cmd = serde_json::json!({
            "command": command,
            "args": args,
            "request_id": request_id.clone()
        });

        // Send command
        let cmd_json = serde_json::to_string(&cmd)
            .map_err(|e| format!("Failed to serialize command: {}", e))?;

        eprintln!("[Rust] Command JSON: {}", cmd_json);

        if let Some(ref mut stdin) = self.stdin {
            writeln!(stdin, "{}", cmd_json)
                .map_err(|e| format!("Failed to write to Python stdin: {}", e))?;
            stdin.flush()
                .map_err(|e| format!("Failed to flush stdin: {}", e))?;
        } else {
            return Err("Python stdin not available".to_string());
        }

        eprintln!("[Rust] Waiting for Python response...");

        // Read responses from the channel (actions are filtered out by the reader thread)
        let timeout = Duration::from_secs(10);
        let start_time = std::time::Instant::now();
        let max_attempts = 20;

        let receiver = self.response_receiver.as_ref()
            .ok_or("Response receiver not available")?;

        for attempt in 0..max_attempts {
            // Check if we've exceeded timeout
            if start_time.elapsed() > timeout {
                return Err(format!("Timeout waiting for Python response after {:?}", timeout));
            }

            // Try to receive with timeout
            let remaining = timeout.saturating_sub(start_time.elapsed());
            match receiver.recv_timeout(remaining.min(Duration::from_millis(500))) {
                Ok(response_line) => {
                    eprintln!("[Rust] Python response (attempt {}): {}", attempt + 1, response_line.trim());

                    // Skip empty lines
                    if response_line.trim().is_empty() {
                        continue;
                    }

                    let response: IpcResponse = serde_json::from_str(&response_line)
                        .map_err(|e| format!("Failed to parse Python response: {}", e))?;

                    // Check if this response matches our request
                    if response.request_id.as_ref() == Some(&request_id) {
                        eprintln!("[Rust] ✓ Response matched request_id, success={}", response.success);
                        return Ok(response);
                    } else {
                        eprintln!("[Rust] ⚠ Response has wrong request_id! Expected '{}', got '{:?}'. Continuing to read...",
                            request_id, response.request_id);
                    }
                }
                Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
                    // Continue waiting
                    continue;
                }
                Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                    return Err("Python process terminated unexpectedly".to_string());
                }
            }
        }

        Err(format!("Failed to receive matching response for request_id '{}' after {} attempts", request_id, max_attempts))
    }

    fn stop(&mut self) -> Result<(), String> {
        if let Some(mut child) = self.child.take() {
            eprintln!("[Rust] Stopping Python process (PID: {})", child.id());
            child.kill()
                .map_err(|e| format!("Failed to kill Python process: {}", e))?;
            child.wait()
                .map_err(|e| format!("Failed to wait for Python process: {}", e))?;
            eprintln!("[Rust] Python process stopped successfully");
            Ok(())
        } else {
            Err("Python process not running".to_string())
        }
    }
}

impl Drop for PythonProcess {
    fn drop(&mut self) {
        // Ensure Python process is killed when PythonProcess is dropped
        if let Some(mut child) = self.child.take() {
            eprintln!("[Rust] Cleaning up Python process (PID: {}) on drop", child.id());
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

struct AppState {
    python: Arc<Mutex<PythonProcess>>,
    config_path: String,
}

#[tauri::command]
async fn start(state: tauri::State<'_, AppState>) -> Result<IpcResponse, String> {
    eprintln!("[Rust/Tauri] start() command called from frontend");
    let mut python = state.python.lock().unwrap();
    python.send_command("start", serde_json::json!({}))
}

#[tauri::command]
async fn stop(state: tauri::State<'_, AppState>) -> Result<IpcResponse, String> {
    eprintln!("[Rust/Tauri] stop() command called from frontend");
    let mut python = state.python.lock().unwrap();
    python.send_command("stop", serde_json::json!({}))
}

#[tauri::command]
async fn get_status(state: tauri::State<'_, AppState>) -> Result<IpcResponse, String> {
    eprintln!("[Rust/Tauri] get_status() command called from frontend");
    let mut python = state.python.lock().unwrap();
    python.send_command("get_status", serde_json::json!({}))
}

#[tauri::command]
async fn get_settings(state: tauri::State<'_, AppState>) -> Result<IpcResponse, String> {
    let mut python = state.python.lock().unwrap();
    python.send_command("get_settings", serde_json::json!({}))
}

#[tauri::command]
async fn update_settings(state: tauri::State<'_, AppState>, settings: serde_json::Value) -> Result<IpcResponse, String> {
    let mut python = state.python.lock().unwrap();
    python.send_command("update_settings", settings)
}

#[tauri::command]
async fn get_info(state: tauri::State<'_, AppState>) -> Result<IpcResponse, String> {
    let mut python = state.python.lock().unwrap();
    python.send_command("get_info", serde_json::json!({}))
}

#[tauri::command]
async fn get_mappings(state: tauri::State<'_, AppState>) -> Result<IpcResponse, String> {
    let mut python = state.python.lock().unwrap();
    python.send_command("get_mappings", serde_json::json!({}))
}

#[tauri::command]
async fn update_mapping(state: tauri::State<'_, AppState>, gesture: String, enabled: bool) -> Result<IpcResponse, String> {
    let mut python = state.python.lock().unwrap();
    python.send_command("update_mapping", serde_json::json!({
        "gesture": gesture,
        "enabled": enabled
    }))
}

#[tauri::command]
async fn update_mappings(state: tauri::State<'_, AppState>, mappings: serde_json::Value) -> Result<IpcResponse, String> {
    let mut python = state.python.lock().unwrap();
    python.send_command("update_mappings", serde_json::json!({
        "mappings": mappings
    }))
}

#[tauri::command]
async fn get_available_gestures_and_actions(state: tauri::State<'_, AppState>) -> Result<IpcResponse, String> {
    let mut python = state.python.lock().unwrap();
    python.send_command("get_available_gestures_and_actions", serde_json::json!({}))
}

#[tauri::command]
async fn get_habit_alert(state: tauri::State<'_, AppState>) -> Result<IpcResponse, String> {
    let mut python = state.python.lock().unwrap();
    python.send_command("get_habit_alert", serde_json::json!({}))
}

#[tauri::command]
async fn get_cameras(state: tauri::State<'_, AppState>) -> Result<IpcResponse, String> {
    let mut python = state.python.lock().unwrap();
    python.send_command("get_cameras", serde_json::json!({}))
}

#[cfg(target_os = "macos")]
fn check_accessibility_permission() {
    use std::process::Command;

    eprintln!("[Rust] Checking Accessibility permission...");

    // Use osascript to trigger the permission check via AppleScript
    // This will show the system prompt if permission is not granted
    let script = r#"
        use framework "Foundation"
        use framework "ApplicationServices"

        set options to current application's NSDictionary's dictionaryWithObject:true forKey:"AXTrustedCheckOptionPrompt"
        set trusted to current application's AXIsProcessTrustedWithOptions(options)
        return trusted as boolean
    "#;

    match Command::new("osascript")
        .args(["-l", "AppleScript", "-e", script])
        .output()
    {
        Ok(output) => {
            let result = String::from_utf8_lossy(&output.stdout).trim().to_string();
            eprintln!("[Rust] Accessibility permission check result: {}", result);
            if result != "true" {
                eprintln!("[Rust] ⚠ Accessibility permission not granted. Please grant permission and restart the app.");
            }
        }
        Err(e) => {
            eprintln!("[Rust] Failed to check accessibility permission: {}", e);
        }
    }
}

#[cfg(not(target_os = "macos"))]
fn check_accessibility_permission() {
    // No-op on non-macOS platforms
}

fn main() {
    eprintln!("[Rust] ============================================");
    eprintln!("[Rust] Handsi Tauri Application Starting");
    eprintln!("[Rust] ============================================");

    // Check Accessibility permission BEFORE starting Python backend
    // This ensures the permission is requested for the main app, and child processes can inherit it
    #[cfg(target_os = "macos")]
    check_accessibility_permission();

    // Find config path
    let config_path = std::env::var("HANDSI_CONFIG")
        .unwrap_or_else(|_| "config/default.yaml".to_string());

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            eprintln!("[Rust] Running Tauri setup...");

            // Start Python process
            eprintln!("[Rust] Starting Python IPC process...");
            let mut python = PythonProcess::new();

            // Pass app handle only in production mode
            let app_handle = if cfg!(debug_assertions) {
                None
            } else {
                Some(app.handle())
            };

            python.start(&config_path, app_handle)?;

            // Store in app state
            app.manage(AppState {
                python: Arc::new(Mutex::new(python)),
                config_path: config_path.clone(),
            });

            eprintln!("[Rust] Setup complete!");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            start,
            stop,
            get_status,
            get_settings,
            update_settings,
            get_info,
            get_mappings,
            update_mapping,
            update_mappings,
            get_available_gestures_and_actions,
            get_habit_alert,
            get_cameras
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
