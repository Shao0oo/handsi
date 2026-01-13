# Building and Installing Handsi MVP

**Current Status:** macOS only - Linux and Windows are not yet implemented.

This guide covers building and installing the macOS MVP using Tauri.

---

## Prerequisites

1. **Development environment setup:**
   - See [SETUP_TAURI.md](SETUP_TAURI.md) for full details
   - Install Rust: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
   - Install Node.js: `brew install node`
   - Activate conda: `conda activate handsi`

2. **Install Tauri CLI:**
   ```bash
   chmod +x scripts/*.sh
   ./scripts/setup-tauri.sh
   ```

---

## Building the App (macOS)

### Step 1: Run the Build Script

```bash
conda activate handsi
./scripts/build-tauri.sh
```

This creates:
- **App Bundle:** `src-tauri/target/release/bundle/macos/Handsi.app`
- **DMG Installer:** `src-tauri/target/release/bundle/dmg/Handsi_<version>_<arch>.dmg`

### Step 2: Verify Build

```bash
# Check app bundle
ls -la src-tauri/target/release/bundle/macos/Handsi.app

# Check DMG
ls -la src-tauri/target/release/bundle/dmg/
```

---

## Installing to /Applications

### Option 1: Using DMG (Recommended)

1. Open the DMG:
   ```bash
   open src-tauri/target/release/bundle/dmg/Handsi_*.dmg
   ```

2. Drag **Handsi.app** to the **Applications** folder

3. Eject the DMG

4. Launch:
   ```bash
   open /Applications/Handsi.app
   ```

### Option 2: Manual Copy

```bash
# Copy to /Applications
cp -r src-tauri/target/release/bundle/macos/Handsi.app /Applications/

# Launch
open /Applications/Handsi.app
```

---

## First Launch: Required Permissions

macOS will prompt for two permissions on first launch:

### 1. Camera Access (Required)
- **Purpose:** Hand tracking via webcam
- **Location:** System Settings → Privacy & Security → Camera
- **Action:** Enable **Handsi.app** ✓

### 2. Accessibility Access (Required)
- **Purpose:** Mouse/keyboard control and desktop switching
- **Location:** System Settings → Privacy & Security → Accessibility
- **Action:**
  1. Click lock icon to unlock
  2. Click **"+"** and add `/Applications/Handsi.app`
  3. Enable **Handsi.app** ✓

**⚠️ Both permissions are required for Handsi to function.**

---

## Troubleshooting

### "App is damaged and can't be opened"

The app is not code-signed. Remove quarantine:

```bash
xattr -cr /Applications/Handsi.app
open /Applications/Handsi.app
```

### Camera/Actions Not Working

**Check permissions:**
1. System Settings → Privacy & Security → Camera → Handsi.app ✓
2. System Settings → Privacy & Security → Accessibility → Handsi.app ✓
3. Restart Handsi

### Permissions Reset After Rebuilding

Each rebuild creates a new signature, resetting permissions:

1. **Remove old permission:**
   - System Settings → Privacy & Security → Accessibility
   - Remove **Handsi.app** (click **"-"**)

2. **Re-grant permissions:**
   ```bash
   open /Applications/Handsi.app
   ```
   Allow Camera and Accessibility when prompted.

---

## Uninstalling

```bash
# Remove app
rm -rf /Applications/Handsi.app

# Remove user data (optional)
rm -rf ~/Library/Application\ Support/com.handsi.app
```

---

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **macOS** | ✅ **Implemented** | Full MVP functionality |
| **Linux** | ❌ Not Implemented | Planned for future release |
| **Windows** | ❌ Not Implemented | Planned for future release |

---

## Development Mode (No Installation)

Run directly from source without building:

```bash
conda activate handsi
python -m handsi.main --help
```

No permission resets between code changes.
