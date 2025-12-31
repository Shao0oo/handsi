# Building and Distributing Handsi Native App

This guide explains how to build standalone executables for macOS, Windows, and Linux.

## Running the App (Development Mode)

```bash
# Activate conda environment
conda activate handsi

# Launch native app
handsi --app

# Launch with debug mode (shows console and detailed logs)
handsi --app --debug
```

**Settings Persistence:**
- Settings are automatically saved to `config/user_config/config.yaml`
- Changes persist across app restarts
- User config is gitignored (won't be committed)
- Use "Reset to Defaults" button in UI to restore defaults

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
