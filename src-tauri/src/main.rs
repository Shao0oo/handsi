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

    fn start(&mut self, config_path: &str) -> Result<(), String> {
        if self.child.is_some() {
            return Err("Python process already running".to_string());
        }

        eprintln!("[Rust] Starting Python IPC process...");

        // Use system Python (assumes conda environment is active)
        // For production: bundle Python binary and use that instead
        // Get project root (parent of src-tauri directory)
        let current_exe = std::env::current_exe()
            .map_err(|e| format!("Failed to get current exe: {}", e))?;
        let exe_dir = current_exe.parent()
            .ok_or("Failed to get exe parent directory".to_string())?;

        // In dev mode, we're in src-tauri/target/debug/, need to go up to project root
        // In production, we'd be in the app bundle
        let project_root = if exe_dir.ends_with("target/debug") || exe_dir.ends_with("target\\debug") {
            // Go up from target/debug -> target -> src-tauri -> project_root
            exe_dir.parent()
                .and_then(|p| p.parent())
                .and_then(|p| p.parent())
                .ok_or("Failed to find project root".to_string())?
        } else {
            exe_dir
        };

        eprintln!("[Rust] Project root: {:?}", project_root);
        eprintln!("[Rust] Config path: {}", config_path);
        eprintln!("[Rust] Command: python -m handsi.main --ipc stdio --config {}", config_path);

        // Add project src/ directory to PYTHONPATH so Python can find handsi module
        let src_path = project_root.join("src");
        eprintln!("[Rust] Adding to PYTHONPATH: {:?}", src_path);

        let mut child = Command::new("python")
            .args(&["-m", "handsi.main", "--ipc", "stdio", "--config", config_path])
            .current_dir(project_root)
            .env("PYTHONPATH", &src_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start Python process: {}", e))?;

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

        eprintln!("[Rust] Sending command to Python: {}", command);

        let cmd = IpcCommand {
            command: command.to_string(),
            args,
        };

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

        // Read response
        if let Some(ref mut stdout) = self.stdout {
            let mut response_line = String::new();
            stdout.read_line(&mut response_line)
                .map_err(|e| format!("Failed to read from Python stdout: {}", e))?;

            eprintln!("[Rust] Python response: {}", response_line.trim());

            let response: IpcResponse = serde_json::from_str(&response_line)
                .map_err(|e| format!("Failed to parse Python response: {}", e))?;

            eprintln!("[Rust] Response parsed successfully: success={}", response.success);

            Ok(response)
        } else {
            Err("Python stdout not available".to_string())
        }
    }

    fn stop(&mut self) -> Result<(), String> {
        if let Some(mut child) = self.child.take() {
            child.kill()
                .map_err(|e| format!("Failed to kill Python process: {}", e))?;
            child.wait()
                .map_err(|e| format!("Failed to wait for Python process: {}", e))?;
            Ok(())
        } else {
            Err("Python process not running".to_string())
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

fn main() {
    eprintln!("[Rust] ============================================");
    eprintln!("[Rust] Handsi Tauri Application Starting");
    eprintln!("[Rust] ============================================");

    // Find config path
    let config_path = std::env::var("HANDSI_CONFIG")
        .unwrap_or_else(|_| "config/default.yaml".to_string());

    tauri::Builder::default()
        .setup(move |app| {
            eprintln!("[Rust] Running Tauri setup...");

            // Open DevTools automatically in dev mode
            #[cfg(debug_assertions)]
            {
                eprintln!("[Rust] Dev mode: Opening DevTools");
                let window = app.get_webview_window("main").unwrap();
                window.open_devtools();
            }

            // Start Python process
            eprintln!("[Rust] Starting Python IPC process...");
            let mut python = PythonProcess::new();
            python.start(&config_path)?;

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
            update_mapping
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
