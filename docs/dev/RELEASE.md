# Creating GitHub Releases for Handsi

This document explains how to create automated releases that users can download with one click.

---

## Overview

When you push a version tag (e.g., `v0.1.0`), GitHub Actions will:
1. Build the Python backend (PyInstaller)
2. Build the Tauri app (macOS .app + DMG)
3. Create a GitHub Release
4. Upload the DMG installer

**User Experience:**
- Visit GitHub Releases page
- Download DMG
- Drag to Applications
- Done!

---

## Creating Your First Release

### Step 1: Ensure Version Consistency

Make sure the version is synced across these files:

**`package.json`:**
```json
{
  "version": "0.1.x"
}
```

**`pyproject.toml`:**
```toml
[project]
version = "0.1.x"
```

**`src-tauri/tauri.conf.json`:**
```json
{
  "version": "0.1.x"
}
```

### Step 2: Commit Your Changes

```bash
git add .
git commit -m "Prepare for v0.1.x release"
git push
```

### Step 3: Create and Push a Git Tag

```bash
# Create a version tag
git tag v0.1.x

# Push the tag to GitHub (triggers the workflow)
git push --tags
```

### Step 4: Monitor the Build

1. Go to your GitHub repository
2. Click **Actions** tab
3. You'll see "Release Handsi" workflow running
4. Build takes ~10-15 minutes

### Step 5: Release is Ready!

Once complete:
1. Click **Releases** (right sidebar)
2. You'll see `v0.1.x` with the DMG attached
3. Share the release URL with users

---

## What Gets Released

The workflow creates:
- **DMG Installer**: `Handsi_0.1.x_aarch64.dmg` (Apple Silicon)
- **Source Code**: Automatic GitHub archive (zip/tar.gz)

**Currently supported:**
- ✅ macOS Apple Silicon (M1/M2/M3)

**Future:**
- ⏳ macOS Intel (x86_64)
- ⏳ Windows
- ⏳ Linux

---

## Release Checklist

Before creating a release, verify:

- [ ] Version numbers match in `package.json`, `pyproject.toml`, `tauri.conf.json`
- [ ] All changes committed and pushed to `main` (or your release branch)
- [ ] App works locally: `./scripts/build-tauri.sh` succeeds
- [ ] Update CHANGELOG.md (optional but recommended)

---

## Workflow Configuration

The workflow is defined in [`.github/workflows/release.yml`](../.github/workflows/release.yml).

### Trigger Points

**Automatic:**
- Any tag starting with `v` (e.g., `v1.0.0`, `v2.3.1-beta`)

**Manual:**
- Go to Actions → Release Handsi → Run workflow

### Environment

- **Runner:** `macos-latest` (GitHub-hosted)
- **Python:** 3.11 (via Miniconda)
- **Node.js:** 20
- **Rust:** Latest stable

---

## Versioning Scheme

We use [Semantic Versioning](https://semver.org/):

- **Major** (1.0.0): Breaking changes
- **Minor** (0.1.0): New features (backward-compatible)
- **Patch** (0.1.1): Bug fixes

**Pre-releases:**
- `v0.1.0-alpha`: Alpha release
- `v0.1.0-beta`: Beta release
- `v0.1.0-rc.1`: Release candidate

---

## Code Signing (Future)

Currently, releases are **not code-signed**. Users will see:
> "Handsi.app cannot be opened because it is from an unidentified developer"

**Workaround for users:**
- Run `xattr -cr /Applications/Handsi.app`

**To add code signing:**
1. Get Apple Developer Account ($99/year)
2. Create certificates
3. Add secrets to GitHub:
   - `APPLE_CERTIFICATE`
   - `APPLE_CERTIFICATE_PASSWORD`
   - `APPLE_ID`
   - `APPLE_PASSWORD`
4. Update workflow with signing configuration

---

## Troubleshooting

### Workflow Fails at PyInstaller Step

**Symptom:** `ModuleNotFoundError: No module named 'handsi'`

**Fix:** Ensure `pip install -e .` runs before PyInstaller

### DMG Not Attached to Release

**Symptom:** Release created but no DMG file

**Fix:** Check Tauri build logs for errors. Ensure `npm run build` succeeds.

### Version Mismatch

**Symptom:** DMG filename shows wrong version

**Fix:** Update version in `tauri.conf.json` and push a new tag

---

## Example: Creating v0.2.0

```bash
# 1. Update versions in package.json, pyproject.toml, tauri.conf.json
# 2. Commit changes
git add .
git commit -m "Bump version to 0.2.0"
git push

# 3. Create and push tag
git tag v0.2.0
git push --tags

# 4. Wait for workflow to complete (~15 min)
# 5. Visit https://github.com/yourname/handsi/releases
# 6. Share the release!
```

---

## Future Enhancements

- [ ] Universal binary (Intel + Apple Silicon in one DMG)
- [ ] Code signing and notarization
- [ ] Windows installer (.exe)
- [ ] Linux AppImage/deb/rpm
- [ ] Auto-update functionality (Tauri Updater plugin)
- [ ] Changelog automation (from git commits)

---

## Questions?

- Check workflow logs in GitHub Actions
- Review [Tauri Action docs](https://github.com/tauri-apps/tauri-action)
- See [BUILD.md](BUILD.md) for local building
