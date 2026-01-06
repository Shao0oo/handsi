# Building and Distributing Handsi Native App

**⚠️ IMPORTANT: Handsi now uses Tauri instead of PyInstaller!**

This guide covers the **new Tauri build system**. For the old PyInstaller method (deprecated), see the end of this document.

---

## Building with Tauri (Recommended)

### Prerequisites

See [SETUP_TAURI.md](SETUP_TAURI.md) for full setup instructions.

**Quick setup:**
```bash
conda activate handsi
chmod +x scripts/*.sh
./scripts/setup-tauri.sh
```

### Build for Your Platform

```bash
# Build Tauri app for current platform
./scripts/build-tauri.sh

# Output will be in dist/ directory:
# - macOS: dist/Handsi.app + dist/Handsi.dmg
# - Windows: dist/Handsi.exe (if built on Windows)
# - Linux: dist/handsi (if built on Linux)
```

## Platform-Specific Notes

### macOS

**Output:** `dist/Handsi.app`

**To run:**
```bash
open dist/Handsi.app
```

**To create DMG installer:**
```bash
# Install create-dmg
brew install create-dmg

# Create DMG
create-dmg \
  --volname "Handsi Installer" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "Handsi.app" 175 120 \
  --hide-extension "Handsi.app" \
  --app-drop-link 425 120 \
  "Handsi-1.0.0.dmg" \
  "dist/"
```

**Permissions on First Launch:**
The app will request two permissions on first launch:
1. **Camera** - For hand tracking (required)
2. **Accessibility** - For mouse/keyboard/desktop switching (required)

**Note:** If you rebuild the app, see the "Permission Reset Warning" section below.

## ⚠️ Permission Reset Warning (macOS)

**IMPORTANT:** Every time you rebuild the app with `pyinstaller handsi.spec`, macOS treats it as a **completely new app** with a different code signature. All permissions are reset and must be re-granted.

### Symptoms of Stale Permissions

After rebuilding, you may experience:
- ✅ Thumbs up/down work (internal state changes only)
- ❌ Mouse movement doesn't work (cursor doesn't move)
- ❌ Click/scroll/swipe don't work (no system control)
- ⚠️ Logs show "Action executed" but nothing happens on screen

This means macOS is **silently blocking** the app because it has stale/missing permissions.

### How to Fix

**Step 1: Remove old permissions**
1. Open: **System Settings → Privacy & Security → Accessibility**
2. Find "Handsi" or "Handsi.app" in the list
3. Click the **(-) button** to remove it
4. This clears the stale permission entry

**Step 2: Re-grant permissions**
1. Launch the rebuilt app: `open dist/Handsi.app`
2. macOS will automatically prompt for:
   - **Accessibility** permission (for mouse/keyboard/desktop switching)
   - **Camera** permission (for hand tracking)
3. Click **"Allow"** or **"OK"** for each prompt

**Step 3: Verify**
Check these settings are enabled:
- **System Settings → Privacy & Security → Accessibility**: Handsi.app ✓
- **System Settings → Privacy & Security → Camera**: Handsi.app ✓

**Note:** Desktop switching (swipe gestures) now uses the same Accessibility permission as mouse/keyboard control, so no separate System Events permission is needed.

### When This Matters

- ✅ After rebuilding with `pyinstaller handsi.spec`
- ✅ After cleaning and rebuilding (`pyinstaller --clean handsi.spec`)
- ❌ NOT needed for development mode (`handsi --app` via Terminal)

**Development Tip:** Use `handsi --app` during development to avoid permission resets across code changes.

### Windows

**Output:** `dist/Handsi/Handsi.exe` (directory)

**To run:**
```cmd
dist\Handsi\Handsi.exe
```

**To create installer:**
```bash
# Install NSIS (Nullsoft Scriptable Install System)
# Download from: https://nsis.sourceforge.io/

# Create installer script (example):
# See: https://nsis.sourceforge.io/Examples
```

### Linux

**Output:** `dist/handsi/handsi` (directory)

**To run:**
```bash
chmod +x dist/handsi/handsi
./dist/handsi/handsi
```

**To create .deb package:**
```bash
# Install fpm
gem install fpm

# Create .deb
fpm -s dir -t deb -n handsi -v 1.0.0 \
  --prefix /opt/handsi \
  dist/handsi/=/opt/handsi
```

**To create .rpm package:**
```bash
# Create .rpm
fpm -s dir -t rpm -n handsi -v 1.0.0 \
  --prefix /opt/handsi \
  dist/handsi/=/opt/handsi
```


## Troubleshooting

**"App is damaged and can't be opened" (macOS)**
```bash
# Remove quarantine attribute
xattr -cr dist/Handsi.app
```

**Missing dependencies error**
- Make sure you built with PyInstaller, not just copying Python files
- Check that `handsi.spec` includes all data files

**WebEngine not loading**
- Verify PySide6 was installed correctly
- Check that `qwebchannel.js` is accessible (bundled in Qt)

**Camera not working**
- Ensure camera permissions are granted
- Check system camera access settings

## Modifying the UI

The UI files are located in `src/handsi/ui/web/`:
- `index.html` - Structure
- `styles.css` - Styling
- `app.js` - Logic

After modifying, rebuild with PyInstaller to bundle the changes.
