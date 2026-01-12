// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use tauri::Manager;

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
    stdout: Option<BufReader<std::process::ChildStdout>>,
}

impl PythonProcess {
    fn new() -> Self {
        PythonProcess {
            child: None,
            stdin: None,
            stdout: None,
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
        self.stdout = Some(BufReader::new(stdout));

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
        use std::time::{SystemTime, UNIX_EPOCH};
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

        // Read responses with timeout to prevent hanging forever
        use std::time::Duration;
        use std::io::{BufRead as _, ErrorKind};

        let timeout = Duration::from_secs(10); // 10 second timeout
        let start_time = std::time::Instant::now();
        let max_attempts = 20;  // Prevent infinite loop

        for attempt in 0..max_attempts {
            // Check if we've exceeded timeout
            if start_time.elapsed() > timeout {
                return Err(format!("Timeout waiting for Python response after {:?}", timeout));
            }

            if let Some(ref mut stdout) = self.stdout {
                let mut response_line = String::new();

                // Try to read line with short timeout
                match stdout.read_line(&mut response_line) {
                    Ok(0) => {
                        // EOF - Python process died
                        return Err("Python process terminated unexpectedly".to_string());
                    }
                    Ok(_) => {
                        eprintln!("[Rust] Python response (attempt {}): {}", attempt + 1, response_line.trim());

                        // Skip empty lines
                        if response_line.trim().is_empty() {
                            eprintln!("[Rust] Warning: Got empty line from Python, continuing...");
                            std::thread::sleep(Duration::from_millis(100));
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
                    Err(e) if e.kind() == ErrorKind::WouldBlock => {
                        // Non-blocking read, no data available yet
                        std::thread::sleep(Duration::from_millis(100));
                        continue;
                    }
                    Err(e) => {
                        return Err(format!("Failed to read from Python stdout: {}", e));
                    }
                }
            } else {
                return Err("Python stdout not available".to_string());
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

fn main() {
    eprintln!("[Rust] ============================================");
    eprintln!("[Rust] Handsi Tauri Application Starting");
    eprintln!("[Rust] ============================================");

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
            get_available_gestures_and_actions
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
