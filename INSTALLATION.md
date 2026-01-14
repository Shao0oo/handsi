# Installing Handsi

Control your Mac using hand gestures — no mouse, no keyboard needed.

---

## Download and Install

If you are updating to a newer version or reinstalling — jump to [Reinstalling or updating](#reinstallation-or-updating-to-newer-release) 

### 1. Download the Installer

Visit the [**Releases page**](https://github.com/Shao0oo/handsi/releases) and download the DMG for your Mac:

| Your Mac Chip | Download File |
|---------------|---------------|
| **Apple Silicon** (M1/M2/M3/M4) | `Handsi_x.x.x_aarch64.dmg` |
| **Intel** | `Handsi_x.x.x_x86_64.dmg` |

**Not sure which chip you have?**
- Click Apple menu () → **About This Mac**
- Look for "Chip" - if it says "Apple M1/M2/M3", choose Apple Silicon
- If it says "Processor" with "Intel", choose Intel

### 2. Install the App

Open the downloaded DMG and drag **Handsi.app** to your **Applications** folder.

### 3. First Launch

macOS will block the app because it's not code-signed. **This is normal.**

**To open Handsi for the first time:**

1. Open **Terminal** (Applications → Utilities → Terminal)
2. Paste this command and press Enter:

```bash
xattr -cr /Applications/Handsi.app
```

3. Launch Handsi from Applications or run:

```bash
open /Applications/Handsi.app
```

### 4. Grant Permissions

Handsi needs two permissions to work:

**Camera Access** (Required)
- macOS will prompt you on first launch
- Or go to: **System Settings → Privacy & Security → Camera**
- Enable **Handsi** ✓

**Accessibility Access** (Required)
- macOS will prompt you on first launch
- Or go to: **System Settings → Privacy & Security → Accessibility**
- Click the lock icon to make changes
- Click **"+"** and add `/Applications/Handsi.app`
- Enable **Handsi** ✓

**Reload Handsi** after granting permissions.
- Turn detection off and back on  

---

## Reinstallation or Updating to Newer Release

macOS permissions will have stale accessibility permissions from previous installation. We will need to delete them. 

The following steps should be done **preferably before reinstallation**. 

### Remove Permissions:
- Open settings
- Open privacy and security
- Open accessibility 
  - Click on Handsi 
  - Click on the small - at the bottom of the accesibility window
  - Remove Handsi from accessibility
- Continue with installing handsi

---

## Configuration & Settings

Your settings are automatically saved to `~/.handsi/config.yaml`

- **Settings persist** across app updates and restarts
- **Edit settings** through the app's Settings panel (auto-saves)
- **Manual editing:** You can also edit `~/.handsi/config.yaml` directly
- **Reset to defaults:** Delete `~/.handsi/config.yaml` and restart the app

---

## Uninstalling

```bash
# Remove the app
rm -rf /Applications/Handsi.app

# (Optional) Remove user data and settings
rm -rf ~/.handsi
```

---

## For Developers

Want to build from source or contribute?

See [**Developer Installation Guide**](docs/dev/DEVELOPER_INSTALLATION.md)

---

## Troubleshooting

### "Handsi.app is damaged and can't be opened"

Run the xattr command again:

```bash
xattr -cr /Applications/Handsi.app
open /Applications/Handsi.app  # or open app by clicking
```

### Camera or Gestures Not Working

1. Check permissions: **System Settings → Privacy & Security**
2. Ensure **Camera** and **Accessibility** are enabled for Handsi
3. Restart the app

### Permissions Reset After Update

Each app update may require re-granting permissions:

1. Remove old permission in **System Settings → Accessibility**
2. Re-launch Handsi and allow permissions when prompted

---

## Need Help?

- [Architecture Documentation](docs/ARCHITECTURE.md)
- [Report an Issue](https://github.com/Shao0oo/handsi/issues)
