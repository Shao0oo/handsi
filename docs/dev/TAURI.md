# Tauri Development Guide

This document covers Tauri architecture, setup details, and migration information from the legacy PySide6 implementation.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Setup Details](#setup-details)
- [IPC Protocol](#ipc-protocol)
- [Python Backend Bundling](#python-backend-bundling)
- [Migration from PySide6](#migration-from-pyside6)
- [Troubleshooting](#troubleshooting)

---

## Overview

**What is Tauri?**
Tauri is a framework for building lightweight desktop apps using web technologies (HTML/CSS/JS) with a Rust backend. Unlike Electron, it uses the OS's native webview instead of bundling Chromium.

**Why Tauri for Handsi?**

| Metric | Old (PySide6) | New (Tauri) |
|--------|---------------|-------------|
| **Bundle size** | ~200MB | ~50MB |
| **Startup time** | 5-10 seconds | <1 second |
| **Tech stack** | Qt WebEngine + Python | Native WebView + Rust + Python |
| **Memory** | ~300MB | ~100MB |

**Benefits:**
- ✅ **4x smaller** downloads
- ✅ **10x faster** startup
- ✅ **Better security** (Tauri's sandboxing)
- ✅ **Native performance** (Rust instead of Python GUI)
- ✅ **Simpler frontend** (async/await vs QWebChannel callbacks)

---

## Architecture

```
┌──────────────────────────────────┐
│   Tauri Frontend (HTML/CSS/JS)   │  src/index.html, app.js, styles.css
│   Rendered in Native WebView     │  (WKWebView on macOS)
└────────────┬─────────────────────┘
             │ Tauri Invoke API
┌────────────┴─────────────────────┐
│   Tauri Backend (Rust)            │  src-tauri/src/main.rs
│   - Command handlers              │  - start, stop, get_status, etc.
│   - Spawns Python subprocess      │  - Manages IPC communication
└────────────┬─────────────────────┘
             │ IPC (stdin/stdout JSON)
┌────────────┴─────────────────────┐
│   Python Backend                  │  src/handsi/
│   - Hand tracking (MediaPipe)     │  - Vision pipeline
│   - Gesture recognition           │  - Action execution
│   - IPC server (stdio)            │  - State management
└───────────────────────────────────┘
```

### Data Flow

**Example: User clicks "Start Tracking"**

1. **Frontend** (JS):
   ```javascript
   await invoke('start');  // Call Rust
   ```

2. **Rust** (main.rs):
   ```rust
   #[tauri::command]
   fn start(state: State<AppState>) -> Result<()> {
       send_to_python({"command": "start", "args": {}})
   }
   ```

3. **Python** (ipc_server.py):
   ```python
   command = json.loads(stdin.readline())
   if command['command'] == 'start':
       controller.start()
       print(json.dumps({"success": true}))
   ```

4. **Response flows back:** Python → Rust → Frontend

---

## Setup Details

### System Requirements

- **macOS**: 10.15+ (Catalina or newer)
- **Node.js**: v20+ (for Tauri CLI)
- **Rust**: 1.70+ (for Tauri compilation)
- **Python**: 3.11 (for backend)

### Installation

See [DEVELOPER_INSTALLATION.md](DEVELOPER_INSTALLATION.md) for full setup.

**Quick version:**
```bash
conda activate handsi
./scripts/setup-tauri.sh
```

### Directory Structure

```
handsi/
├── package.json             # Node.js/Tauri dependencies
├── src/                     # Frontend (HTML/CSS/JS)
│   ├── index.html          # Main UI
│   ├── styles.css
│   └── app.js              # Tauri invoke API
├── src-tauri/              # Rust/Tauri backend
│   ├── Cargo.toml          # Rust dependencies
│   ├── tauri.conf.json     # Tauri config
│   ├── src/main.rs         # Rust IPC handlers
│   ├── icons/              # App icons
│   └── bundle/             # Python bundling
│       └── handsi-backend.spec  # PyInstaller spec
└── src/handsi/             # Python backend (hand tracking)
    ├── main.py             # Entry point (added --ipc mode)
    └── ui/
        ├── ipc_server.py   # NEW: stdio IPC server
        └── controller.py   # Reused from Qt version
```

---

## IPC Protocol

Tauri (Rust) and Python communicate via **stdio** using **JSON lines**.

### Command Format (Rust → Python via stdin)

```json
{"command": "start", "args": {}}
{"command": "update_settings", "args": {"sensitivity": 0.8}}
{"command": "get_status", "args": {}}
```

### Response Format (Python → Rust via stdout)

```json
{"success": true, "data": {"status": "running", "fps": 30}}
{"success": false, "error": "Camera not available"}
```

### Available Commands

| Command | Args | Returns |
|---------|------|---------|
| `start` | `{}` | `{"success": true}` |
| `stop` | `{}` | `{"success": true}` |
| `get_status` | `{}` | `{"success": true, "data": {...}}` |
| `get_settings` | `{}` | `{"success": true, "data": {...}}` |
| `update_settings` | `{"key": "value"}` | `{"success": true}` |
| `get_mappings` | `{}` | `{"success": true, "data": [...]}` |
| `update_mapping` | `{"gesture": "...", "action": "..."}` | `{"success": true}` |
| `get_info` | `{}` | `{"success": true, "data": {...}}` |

### Implementation

**Rust side** (`src-tauri/src/main.rs`):
```rust
#[tauri::command]
async fn start(state: State<'_, AppState>) -> Result<JsonValue, String> {
    let mut backend = state.backend.lock().unwrap();
    let result = backend.send_command("start", json!({})).await?;
    Ok(result)
}
```

**Python side** (`src/handsi/ui/ipc_server.py`):
```python
class IpcServer:
    def run(self):
        for line in sys.stdin:
            try:
                command = json.loads(line)
                response = self.handle_command(command)
                print(json.dumps(response), flush=True)
            except Exception as e:
                error_response = {"success": False, "error": str(e)}
                print(json.dumps(error_response), flush=True)

    def handle_command(self, command):
        cmd = command.get('command')
        args = command.get('args', {})

        if cmd == 'start':
            self.controller.start()
            return {"success": True}
        # ... other commands
```

---

## Python Backend Bundling

The Python backend is bundled as a standalone executable using **PyInstaller**.

### Why Bundle?

Without bundling, users would need:
- Install Python
- Install conda
- Create environment
- Install dependencies

With bundling:
- Download DMG → Drag to Applications → Done!

### Build Process

**During development:**
- Uses system Python from conda: `python -m handsi.main --ipc stdio`
- Requires `PYTHONPATH` set to `src/`

**During production build:**
1. PyInstaller bundles Python + dependencies into single binary
2. Binary placed in `src-tauri/bin/handsi-backend-<arch>`
3. Tauri includes binary in `.app` bundle
4. Runtime: Tauri launches binary directly (no Python install needed)

### PyInstaller Spec File

Location: `src-tauri/bundle/handsi-backend.spec`

**Key features:**
- Bundles all dependencies (OpenCV, MediaPipe, PyObjC, etc.)
- Detects architecture (aarch64 vs x86_64)
- Creates standalone binary (~196MB)
- Includes matplotlib font cache (faster startup)

**Build command:**
```bash
pyinstaller src-tauri/bundle/handsi-backend.spec \
    --distpath src-tauri/bin \
    --clean
```

**Output:**
- `src-tauri/bin/handsi-backend-aarch64-apple-darwin` (Apple Silicon)
- `src-tauri/bin/handsi-backend-x86_64-apple-darwin` (Intel)

### Tauri Integration

**tauri.conf.json:**
```json
{
  "bundle": {
    "externalBin": [
      "bin/handsi-backend"
    ]
  }
}
```

Tauri automatically:
1. Finds `handsi-backend-<target-triple>` in `bin/`
2. Bundles it into `.app/Contents/MacOS/`
3. Strips the target triple suffix
4. Launches it as subprocess

---

## Migration from PySide6

### What Changed

**Removed:**
- ❌ `src/handsi/ui/qt_app.py` - Qt GUI
- ❌ `src/handsi/ui/qt_bridge.py` - QWebChannel bridge
- ❌ `src/handsi/ui/web/` - Web files (moved to `src/`)
- ❌ `handsi.spec` - Old PyInstaller spec
- ❌ `PySide6` dependency

**Added:**
- ✅ `src-tauri/` - Tauri project
- ✅ `src/handsi/ui/ipc_server.py` - stdio IPC server
- ✅ `src/` - Frontend (HTML/CSS/JS)
- ✅ `package.json` - npm dependencies
- ✅ `src-tauri/bundle/handsi-backend.spec` - New PyInstaller spec

### Frontend Changes

**Before (QWebChannel):**
```javascript
// Initialize bridge
new QWebChannel(qt.webChannelTransport, (channel) => {
    bridge = channel.objects.bridge;

    // Call Python method (callback-based)
    bridge.start((resultJson) => {
        const result = JSON.parse(resultJson);
        console.log(result);
    });
});
```

**After (Tauri):**
```javascript
// Import Tauri API
const { invoke } = window.__TAURI__.core;

// Call Python command (async/await)
const result = await invoke('start');
console.log(result);
```

**Much simpler!** Async/await instead of callbacks, no JSON stringification.

### Python Changes

**main.py:**

Added `--ipc` mode:
```python
parser.add_argument("--ipc", type=str, choices=["stdio"])

if args.ipc:
    from handsi.ui.ipc_server import run_ipc_server
    run_ipc_server(config_path)
```

**New file:** `ipc_server.py`

Reads JSON from stdin, calls controller methods, writes JSON to stdout.

```python
class IpcServer:
    def __init__(self, config_path):
        self.controller = HandsiController(config_path)

    def run(self):
        for line in sys.stdin:
            command = json.loads(line)
            response = self.handle_command(command)
            print(json.dumps(response), flush=True)
```

### controller.py

Mostly **unchanged** — all the core logic (start/stop, settings, mappings) was reused from the Qt version. Only the communication layer changed.

---

## Troubleshooting

### Tauri window doesn't open

**Check:**
- Rust installed: `cargo --version`
- Node.js installed: `node --version`
- npm dependencies: `npm install`

**Look for errors:**
```bash
npm run dev  # Check console output
```

### Python process not starting

**Check:**
- Conda environment active: `conda activate handsi`
- Python runs manually:
  ```bash
  python -m handsi.main --ipc stdio --config config/default.yaml
  ```
- Logs: `~/.handsi/logs/handsi_ipc.log`

### IPC communication fails

**Debug:**
- Check Python stdout/stderr in Tauri console
- Verify JSON format is correct
- Check Rust command handlers in `main.rs`
- Test Python IPC manually:
  ```bash
  echo '{"command": "get_status", "args": {}}' | python -m handsi.main --ipc stdio
  ```

### Camera/Accessibility not working

**In dev mode:**
- Grant Terminal permissions (not Handsi.app)
- System Settings → Privacy & Security → Camera → Terminal ✓
- System Settings → Privacy & Security → Accessibility → Terminal ✓

**In production (.app):**
- Grant Handsi.app permissions
- System Settings → Privacy & Security → Camera → Handsi ✓
- System Settings → Privacy & Security → Accessibility → Handsi ✓

### Build fails

**PyInstaller errors:**
```bash
conda activate handsi
pip install pyinstaller
pyinstaller src-tauri/bundle/handsi-backend.spec --clean
```

**Rust/Tauri errors:**
```bash
rustup update
cargo clean
npm run build
```

---

## Development Tips

### Hot Reload

Frontend changes (HTML/CSS/JS) auto-reload in dev mode:
```bash
./scripts/dev-tauri.sh
```

Python changes require restart:
```bash
# Stop dev-tauri.sh (Ctrl+C)
./scripts/dev-tauri.sh  # Restart
```

### Debugging

**Frontend console:**
- Right-click in app → Inspect Element → Console

**Python logs:**
- `~/.handsi/logs/handsi_ipc.log`

**Rust logs:**
```bash
RUST_LOG=debug npm run dev
```

### Testing IPC Commands

**Manual test:**
```bash
python -m handsi.main --ipc stdio --config config/default.yaml
# Type JSON commands:
{"command": "get_status", "args": {}}
# Press Enter, see response
```

---

## Known Issues / TODOs

1. **Missing features** from Qt version:
   - ⏳ Reset to defaults button (easy to add)
   - ⏳ Auto-restart on settings change (not needed - applies live)

2. **Status polling**: Frontend polls every 500ms. Could use Tauri events for push updates.

3. **Error handling**: Simplified in Rust. Could be more robust.

4. **Code signing**: Not code-signed. Users see "unidentified developer" warning.

5. **Notarization**: Not notarized with Apple. Required for wide distribution.

---

## Next Steps

- **Build for production:** See [BUILD.md](BUILD.md)
- **Create releases:** See [RELEASE.md](RELEASE.md)
- **Full dev setup:** See [DEVELOPER_INSTALLATION.md](DEVELOPER_INSTALLATION.md)

---

For questions or issues, [create a GitHub issue](https://github.com/Shao0oo/handsi/issues).
