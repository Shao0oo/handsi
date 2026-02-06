# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Handsi Python backend.

This bundles the entire Python backend (handsi module + dependencies)
into a single executable for distribution with Tauri.

Usage:
    pyinstaller src-tauri/bundle/handsi-backend.spec

Output:
    - macOS M-series: handsi-backend-aarch64-apple-darwin
    - macOS Intel: handsi-backend-x86_64-apple-darwin
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

# Determine target architecture
if sys.platform == 'darwin':
    import platform
    arch = platform.machine()
    if arch == 'arm64':
        target_triple = 'aarch64-apple-darwin'
    else:
        target_triple = 'x86_64-apple-darwin'
else:
    raise RuntimeError("This spec is designed for macOS only")

binary_name = f'handsi-backend-{target_triple}'

# Project root directory
project_root = Path(SPECPATH).parent.parent

# Collect all data files from mediapipe (includes .tflite models)
mediapipe_datas, mediapipe_binaries, mediapipe_hiddenimports = collect_all('mediapipe')

# Collect all data files from opencv
opencv_datas, opencv_binaries, opencv_hiddenimports = collect_all('cv2')

# Collect all data files from PyYAML
pyyaml_datas, pyyaml_binaries, pyyaml_hiddenimports = collect_all('yaml')

# Combine all data files
datas = []
datas += mediapipe_datas
datas += opencv_datas
datas += pyyaml_datas

# Combine all binaries
binaries = []
binaries += mediapipe_binaries
binaries += opencv_binaries

# Pre-build matplotlib font cache to avoid slow first-run
# This prevents the "Matplotlib is building the font cache" message
import matplotlib
matplotlib_cache_dir = Path(matplotlib.get_cachedir())
if matplotlib_cache_dir.exists():
    # Include the font cache in the bundle
    datas.append((str(matplotlib_cache_dir), 'matplotlib-cache'))

# Hidden imports (modules that PyInstaller might miss)
hiddenimports = [
    # Core dependencies
    'handsi',
    'handsi.main',
    'handsi.ui.ipc_server',
    'handsi.ui.controller',
    'handsi.core.config',
    'handsi.core.logging',
    'handsi.core.bus',
    'handsi.core.utils',
    'handsi.vision.capture',
    'handsi.vision.tracking',
    'handsi.gestures.infer',
    'handsi.actions.executor',

    # Third-party
    'pydantic',
    'pydantic.json',
    'pydantic_core',
    'typing_extensions',

    # MediaPipe
    *mediapipe_hiddenimports,
    'google.protobuf',
    'google.protobuf.descriptor',
    'google.protobuf.message',

    # OpenCV
    *opencv_hiddenimports,
    'numpy',
    'numpy.core',
    'numpy.core._multiarray_umath',

    # PyYAML
    *pyyaml_hiddenimports,

    # macOS specific
    'objc',
    'Quartz',
    'Foundation',
]

# Analysis: find all imports
a = Analysis(
    [str(project_root / 'src' / 'handsi' / 'main.py')],
    pathex=[str(project_root / 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude GUI libraries (not needed for IPC mode)
        'PySide6',
        'PyQt5',
        'PyQt6',
        'tkinter',
        # matplotlib is needed by mediapipe (drawing_utils)
        # unittest is needed by pyparsing (matplotlib dependency)
        'IPython',
        'jupyter',
        # Exclude test frameworks (but not unittest - it's needed by matplotlib)
        'pytest',
        # Exclude documentation tools
        'sphinx',
        'docutils',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Create PYZ (compressed Python bytecode archive)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create single-file executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=binary_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Don't use UPX compression (causes issues on macOS)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console app (IPC via stdin/stdout)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=arch,
    codesign_identity=None,  # Optional: add code signing later
    entitlements_file=None,
    # Create bundle to add LSUIElement flag (prevents Dock icon)
    bundle_identifier=f'com.handsi.backend.{target_triple}',
)
