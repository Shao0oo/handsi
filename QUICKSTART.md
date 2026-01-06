# Handsi Quick Start

**Contactless desktop control using hand tracking**

---

## First Time Setup

```bash
# 1. Create conda environment
conda create -n handsi python=3.11
conda activate handsi

# 2. Make scripts executable
chmod +x scripts/*.sh

# 3. Run setup (installs everything)
./scripts/setup-tauri.sh
```

---

## Running the App

### GUI Mode (Tauri)
```bash
conda activate handsi
./scripts/dev-tauri.sh
```

### CLI Mode (Background Service)
```bash
conda activate handsi
handsi --cli
```

---

## Building for Distribution

```bash
./scripts/build-tauri.sh
```

Output: `dist/Handsi.app` (macOS), `dist/Handsi.dmg`

---

## Documentation

- **Setup**: [docs/SETUP_TAURI.md](docs/SETUP_TAURI.md)
- **Installation**: [docs/INSTALLATION.md](docs/INSTALLATION.md)
- **Building**: [docs/BUILD.md](docs/BUILD.md)
- **Migration**: [docs/TAURI_MIGRATION.md](docs/TAURI_MIGRATION.md)
- **macOS Setup**: [docs/SETUP_MACOS.md](docs/SETUP_MACOS.md)

---

## Troubleshooting

### "Permission denied" when running scripts
```bash
chmod +x scripts/*.sh
```

### "Conda environment not active"
```bash
conda activate handsi
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

---

## What's Different (Tauri vs Qt)

| Feature | Old (Qt/PyInstaller) | New (Tauri) |
|---------|---------------------|-------------|
| Setup | `pip install -e .[dev]` | `./scripts/setup-tauri.sh` |
| Run dev | `python -m handsi.main` | `./scripts/dev-tauri.sh` |
| Build | `pyinstaller handsi.spec` | `./scripts/build-tauri.sh` |
| Bundle | ~200MB | ~50MB |
| Startup | 5-10s | <1s |

---

For more details, see [docs/SETUP_TAURI.md](docs/SETUP_TAURI.md)
