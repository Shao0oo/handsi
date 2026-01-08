# Handsi Tauri Setup

Quick setup guide for the new Tauri-based GUI.

## Prerequisites

Handsi Tauri requires **system-level** tools that cannot be installed via `pyproject.toml`:

1. **Python 3.11+** (via conda) - For backend
2. **Node.js** - For Tauri CLI and npm packages
3. **Rust** - For Tauri app compilation

**Why not in pyproject.toml?**
- `pyproject.toml` only manages **Python packages** (pip/conda)
- Node.js and Rust are **system tools**, not Python packages
- They must be installed via system package managers (brew, rustup, etc.)

---

## Quick Setup (Automated)

**One-time setup:**

```bash
# 1. Activate conda environment
conda activate handsi

# 2. Make scripts executable (first time only)
chmod +x scripts/*.sh

# 3. Run setup script (installs Node.js, Rust, dependencies)
./scripts/setup-tauri.sh
```

This will:
- ✅ Check Python/conda environment
- ✅ Install Node.js (via Homebrew if missing)
- ✅ Install Rust (via rustup if missing)
- ✅ Install Python dependencies (`pip install -e .`)
- ✅ Install npm dependencies (`npm install`)

---

## Manual Setup (If Automated Fails)

### 1. Install System Tools

**Node.js:**
```bash
brew install node
# Or download from: https://nodejs.org
```

**Rust:**
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
```

### 2. Install Python Dependencies

```bash
conda activate handsi
pip install -e .
```

### 3. Install npm Dependencies

```bash
npm install
```

---

## Running the App

### Development Mode (Hot Reload)

```bash
./scripts/dev-tauri.sh
```

Or manually:
```bash
conda activate handsi
npm run dev
```

### CLI Mode (No GUI)

```bash
conda activate handsi
python -m handsi.main --cli
handsi --cli
```

### Production Build

```bash
./scripts/build-tauri.sh
```

Output: `dist/Handsi.app`

---

## Understanding the Modes

Handsi now has **3 modes**:

| Mode | Command | Description |
|------|---------|-------------|
| **Tauri GUI** | `./scripts/dev-tauri.sh` | New Tauri-based GUI (default for end users) |
| **CLI** | `python -m handsi.main --cli` | Background service, no GUI |
| **IPC** | `python -m handsi.main --ipc stdio` | For Tauri subprocess (automatic) |

**Note:** Running `handsi` or `python -m handsi.main` without flags now shows a message directing you to use Tauri.

---

## What is IPC Mode?

**IPC = Inter-Process Communication**

When you run the Tauri app:
1. **Tauri (Rust)** launches and creates the window
2. **Python** starts as a subprocess: `python -m handsi.main --ipc stdio`
3. They communicate via **stdio** (JSON over stdin/stdout):
   - Tauri → Python: `{"command": "start", "args": {}}`
   - Python → Tauri: `{"success": true, "data": {...}}`

You don't need to run IPC mode manually - Tauri does it automatically!

---

## Troubleshooting

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

### "npm install fails"
```bash
# Clear cache and retry
rm -rf node_modules package-lock.json
npm install
```

### "Tauri build fails"
```bash
# Update Rust
rustup update
cargo clean
npm run build
```

---

## Comparison: Old vs New

| Aspect | Old (PyInstaller) | New (Tauri) |
|--------|-------------------|-------------|
| **Setup** | `pip install -e .[dev]` | `./scripts/setup-tauri.sh` |
| **Run dev** | `python -m handsi.main` | `./scripts/dev-tauri.sh` |
| **Build** | `pyinstaller handsi.spec` | `npm run build` |
| **Bundle size** | ~200MB | ~50MB |
| **Startup time** | 5-10 seconds | <1 second |
| **Tech** | PySide6 + Qt WebEngine | Rust + Native WebView |

---

## Next Steps

1. **Run setup**: `./scripts/setup-tauri.sh`
2. **Test app**: `./scripts/dev-tauri.sh`
3. **Read migration guide**: [TAURI_MIGRATION.md](TAURI_MIGRATION.md)

---

For detailed technical info, see [TAURI_MIGRATION.md](TAURI_MIGRATION.md).
