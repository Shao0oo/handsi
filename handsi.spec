# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Handsi native app.

Usage:
    pyinstaller handsi.spec

This creates a standalone executable bundling:
- Python runtime
- All dependencies (PySide6, Qt WebEngine, mediapipe, opencv, etc.)
- HTML/CSS/JS files
- Config files

Output:
    - macOS: dist/Handsi.app
    - Windows: dist/Handsi.exe
    - Linux: dist/handsi
"""

import sys
import os
from pathlib import Path

# Paths (use SPECPATH which is defined by PyInstaller)
project_root = Path(SPECPATH)
src_dir = project_root / 'src'
web_dir = src_dir / 'handsi' / 'ui' / 'web'
config_dir = project_root / 'config'

# Find MediaPipe installation path
import mediapipe
mediapipe_path = Path(mediapipe.__file__).parent

block_cipher = None

a = Analysis(
    ['src/handsi/main.py'],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        # Include HTML/CSS/JS files
        (str(web_dir / 'index.html'), 'handsi/ui/web'),
        (str(web_dir / 'styles.css'), 'handsi/ui/web'),
        (str(web_dir / 'app.js'), 'handsi/ui/web'),
        # Include default config
        (str(config_dir / 'default.yaml'), 'config'),
        # Include MediaPipe model files (required for hand tracking)
        (str(mediapipe_path / 'modules'), 'mediapipe/modules'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebChannel',
        'PySide6.QtWebEngineCore',
        'mediapipe',
        'cv2',
        'numpy',
        'yaml',
        'pydantic',
        'matplotlib',
        'matplotlib.pyplot',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 'matplotlib',  # Required by mediapipe.solutions.drawing_utils
        'scipy',
        'pandas',
        'jupyter',
        'IPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Platform-specific settings
if sys.platform == 'darwin':
    # macOS
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Handsi',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,  # GUI app
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Handsi',
    )

    app = BUNDLE(
        coll,
        name='Handsi.app',
        icon='src/handsi/ui/icon/handsi_icon.icns',
        bundle_identifier='com.handsi.app',
        info_plist={
            'NSCameraUsageDescription': 'Handsi needs camera access for hand tracking',
            'NSMicrophoneUsageDescription': 'Handsi needs microphone access for voice commands (optional)',
            'NSAppleEventsUsageDescription': 'Handsi uses AppleScript to switch desktops and control system functions',
        },
    )

elif sys.platform == 'win32':
    # Windows
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Handsi',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,  # No console window
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='src/handsi/ui/icon/handsi_icon.ico',
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Handsi',
    )

else:
    # Linux
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='handsi',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,  # No console window
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='handsi',
    )
