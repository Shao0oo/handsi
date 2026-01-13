# Developer Installation Guide

Complete setup guide for developing Handsi from source.

---

## Prerequisites

1. **macOS** (10.15 Catalina or newer)
2. **Conda** or **Miniconda** ([Install here](https://docs.conda.io/en/latest/miniconda.html))
3. **Xcode Command Line Tools**:
   ```bash
   xcode-select --install
   ```

---

## Quick Setup (Automated)

The fastest way to get started:

```bash
# 1. Clone the repository
cd ~/Desktop
git clone https://github.com/Shao0oo/handsi.git
cd handsi

# 2. Create conda environment
conda create -n handsi python=3.11
conda activate handsi

# 3. Make scripts executable
chmod +x scripts/*.sh

# 4. Run setup script (installs everything)
./scripts/setup-tauri.sh
```

This script will:
- ✅ Install Node.js (via Homebrew)
- ✅ Install Rust (via rustup)
- ✅ Install Python dependencies
- ✅ Install npm dependencies

**Continue to [Running the App](#running-the-app)**

---

## Manual Setup

If the automated script fails or you prefer manual control:

### 1. Clone Repository

```bash
cd ~/Desktop
git clone https://github.com/Shao0oo/handsi.git
cd handsi
```

### 2. Create Python Environment

```bash
# Create conda environment
conda create -n handsi python=3.11
conda activate handsi

# Install Handsi in editable mode
pip install -e .
```

This installs all Python dependencies from `pyproject.toml`:
- OpenCV, MediaPipe (computer vision)
- PyYAML, Pydantic (config)
- PyObjC (macOS integration)

### 3. Install Node.js

**Via Homebrew (recommended):**
```bash
brew install node
```

**Or download:** [nodejs.org](https://nodejs.org)

**Verify:**
```bash
node --version  # Should show v20.x or newer
npm --version
```

### 4. Install Rust

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
```

**Verify:**
```bash
cargo --version  # Should show 1.70+ or newer
```

### 5. Install npm Dependencies

```bash
npm install
```

This installs:
- `@tauri-apps/cli` - Tauri CLI
- `@tauri-apps/api` - Tauri JavaScript API

---

## Running the App

### Development Mode (Recommended)

Hot-reload enabled — changes to frontend auto-refresh:

```bash
conda activate handsi
./scripts/dev-tauri.sh
```

Or manually:
```bash
conda activate handsi
npm run dev
```

**Note:** If running from Terminal, you may need to grant Terminal **Accessibility** permissions:
- **System Settings → Privacy & Security → Accessibility**
- Add **Terminal.app** ✓

### CLI Mode (No GUI)

Background service only:

```bash
conda activate handsi
handsi --cli
```

Or:
```bash
python -m handsi.main --cli
```

### Production Build

Build a standalone .app bundle:

```bash
./scripts/build-tauri.sh
```

Output:
- **App**: `src-tauri/target/release/bundle/macos/Handsi.app`
- **DMG**: `src-tauri/target/release/bundle/macos/Handsi_x.x.x_<arch>.dmg`

---

## Project Structure

```
handsi/
├── src/                     # Frontend (HTML/CSS/JS)
│   ├── index.html          # Main UI
│   ├── styles.css
│   └── app.js              # Tauri API calls
├── src-tauri/              # Tauri/Rust backend
│   ├── src/main.rs         # Rust IPC handlers
│   ├── tauri.conf.json     # Tauri config
│   └── bundle/             # Python bundling
│       └── handsi-backend.spec
├── src/handsi/             # Python hand tracking
│   ├── main.py             # Entry point
│   ├── core/               # Core logic
│   ├── vision/             # Computer vision
│   ├── gestures/           # Gesture recognition
│   ├── actions/            # Action execution
│   └── ui/
│       ├── ipc_server.py   # IPC server
│       └── controller.py   # Main controller
├── scripts/                # Build/dev scripts
│   ├── setup-tauri.sh
│   ├── dev-tauri.sh
│   └── build-tauri.sh
├── config/
│   └── default.yaml        # Default configuration
└── pyproject.toml          # Python dependencies
```

---

## Understanding the Modes

Handsi has **3 execution modes**:

| Mode | Command | Description |
|------|---------|-------------|
| **Tauri GUI** | `./scripts/dev-tauri.sh` | Full GUI app (default for users) |
| **CLI** | `handsi --cli` | Background service, no GUI |
| **IPC** | `python -m handsi.main --ipc stdio` | For Tauri subprocess (automatic) |

**How it works:**
1. Tauri (Rust) launches and creates the window
2. Python backend starts as subprocess via IPC
3. They communicate over stdin/stdout using JSON
4. Frontend calls Tauri → Tauri calls Python → Results return

You don't need to run IPC mode manually — Tauri handles it!

---

## Permissions Required

### Camera Access
**Why:** Hand tracking via webcam
**Where:** System Settings → Privacy & Security → Camera → Terminal (for dev) or Handsi (for built app)

### Accessibility Access
**Why:** Mouse/keyboard control, desktop switching
**Where:** System Settings → Privacy & Security → Accessibility → Terminal (for dev) or Handsi (for built app)

**Note:** If running via Terminal (`./scripts/dev-tauri.sh`), grant permissions to **Terminal.app**. If running the built `.app`, grant to **Handsi.app**.

---

## Configuration

Default config: [`config/default.yaml`](../../config/default.yaml)

**Never edit** `config/default.yaml` directly (it's hand-tuned).

To override settings:
- Use the GUI Settings panel (changes auto-save)
- Or create `~/.handsi/config.yaml` (user overrides)

---

## Troubleshooting

### "conda: command not found"
Install Miniconda: https://docs.conda.io/en/latest/miniconda.html

### "Permission denied" when running scripts
```bash
chmod +x scripts/*.sh
```

### "Command not found: node"
```bash
brew install node
```

### "Command not found: cargo"
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
```

### "Conda environment not active"
```bash
conda activate handsi
```

### Camera/Actions not working in dev mode
Grant Terminal **Camera** and **Accessibility** permissions:
- System Settings → Privacy & Security → Camera → Terminal ✓
- System Settings → Privacy & Security → Accessibility → Terminal ✓

### npm install fails
```bash
rm -rf node_modules package-lock.json
npm install
```

### Tauri build fails
```bash
rustup update
cargo clean
npm run build
```

---

## Next Steps

- **Build from source:** See [BUILD.md](BUILD.md)
- **Create releases:** See [RELEASE.md](RELEASE.md)
- **Understand Tauri architecture:** See [TAURI.md](TAURI.md)
- **Implementation details:** See [IMPLEMENTATION.md](IMPLEMENTATION.md)

---

## Development Workflow

**Typical dev cycle:**

1. Make code changes
2. Frontend changes → Auto-reload in dev mode
3. Python changes → Restart dev script
4. Test changes
5. Commit and push

**Before committing:**
- Ensure `conda activate handsi` is active
- Run local build: `./scripts/build-tauri.sh`
- Test the built `.app`

---

For questions or issues, [create a GitHub issue](https://github.com/Shao0oo/handsi/issues).
