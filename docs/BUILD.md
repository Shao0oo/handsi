# Building and Distributing Handsi Native App

This guide explains how to build standalone executables for macOS, Windows, and Linux.

## Building Standalone Executables

### Prerequisites

Install development dependencies (includes PyInstaller):
```bash
conda activate handsi
pip install -e ".[dev]"
```

### Build for Your Platform

```bash
# Build executable for current platform
pyinstaller handsi.spec

# Output will be in dist/ directory:
# - macOS: dist/Handsi.app
# - Windows: dist/Handsi.exe (folder with dependencies)
# - Linux: dist/handsi (folder with dependencies)
```

### Build Options

**One-directory (faster startup, recommended):**
```bash
pyinstaller handsi.spec  # Default
```

**One-file executable (slower startup, but single file):**
```bash
pyinstaller --onefile handsi.spec
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
The app will request three permissions on first launch:
1. **Camera** - For hand tracking (required)
2. **Accessibility** - For mouse/keyboard control (required)
3. **System Events** - For desktop switching (triggered on first swipe gesture)

#### Rebuilding

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
   - **Accessibility** permission (for mouse/keyboard control)
   - **Camera** permission (for hand tracking)
3. Click **"Allow"** or **"OK"** for each prompt
4. Try a **swipe gesture** to trigger the System Events prompt:
   - macOS will ask: "Handsi.app would like to control System Events"
   - Click **"OK"** to grant

**Step 3: Verify**
Check these settings are enabled:
- **System Settings → Privacy & Security → Accessibility**: Handsi.app ✓
- **System Settings → Privacy & Security → Automation → System Events**: Handsi.app ✓
- **System Settings → Privacy & Security → Camera**: Handsi.app ✓

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

## Next Steps

1. **Add Icon:** Create icon files and update `handsi.spec`
   - macOS: `.icns` file
   - Windows: `.ico` file
   - Linux: `.png` file

2. **Code Signing:** Sign executables for distribution
   - macOS: `codesign` with Apple Developer certificate
   - Windows: SignTool with code signing certificate

3. **Auto-Updates:** Implement update checker
   - Check GitHub releases API
   - Download and install updates

4. **Crash Reporting:** Add error tracking
   - Sentry, Rollbar, etc.
