# Installation

**⚠️ IMPORTANT: Handsi now uses Tauri for the GUI!**

## Quick Start (Tauri GUI)

For the **new Tauri-based GUI** (recommended):

See **[SETUP_TAURI.md](SETUP_TAURI.md)** for complete setup instructions.

**Quick version:**
```bash
# 1. Clone the repository
cd ~/Desktop
git clone https://github.com/Shao0oo/handsi.git handsi
cd handsi

# 2. Create conda environment
conda create -n handsi python=3.11
conda activate handsi

# 3. Make scripts executable
chmod +x scripts/*.sh

# 4. Run setup (installs Node.js, Rust, all dependencies)
./scripts/setup-tauri.sh

# 5. Run the app
./scripts/dev-tauri.sh
```

---

## CLI Only (No GUI)

If you only want CLI mode (background service, no GUI):

1. **Clone the repository**
   ```bash
   cd ~/Desktop
   git clone https://github.com/Shao0oo/handsi.git handsi
   cd handsi
   ```

2. **Create conda environment**
   ```bash
   conda create -n handsi python=3.11
   conda activate handsi
   ```

3. **Install Handsi**
   ```bash
   pip install -e .
   ```

4. **Run in CLI mode**
   ```bash
   handsi --cli
   ```

---

## OS-Specific Guides

- **macOS**: [SETUP_MACOS.md](SETUP_MACOS.md) - Camera and accessibility permissions
- **Tauri GUI**: [SETUP_TAURI.md](SETUP_TAURI.md) - Complete Tauri setup
- **Building**: [BUILD.md](BUILD.md) - Build standalone app
<!-- - [SETUP_LINUX.md](SETUP_LINUX.md) -->