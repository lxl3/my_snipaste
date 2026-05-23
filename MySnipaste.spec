# -*- mode: python ; coding: utf-8 -*-

import os
import sys

PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))
BUILD_DIR = os.path.join(PROJECT_DIR, 'build')
TESSERACT_BUNDLE = os.path.join(BUILD_DIR, 'tesseract_bundle')

_tess_bin = []
_tess_data = []
if os.path.isdir(TESSERACT_BUNDLE):
    _tess_bin = [(os.path.join(TESSERACT_BUNDLE, f), 'tesseract')
                 for f in os.listdir(TESSERACT_BUNDLE)
                 if f != 'tessdata' and os.path.isfile(os.path.join(TESSERACT_BUNDLE, f))]
    _tessdata_dir = os.path.join(TESSERACT_BUNDLE, 'tessdata')
    if os.path.isdir(_tessdata_dir):
        _tess_data = [(_tessdata_dir, 'tesseract/tessdata')]

a = Analysis(
    [os.path.join(PROJECT_DIR, 'main.py')],
    pathex=[],
    binaries=_tess_bin,
    datas=[(os.path.join(PROJECT_DIR, 'assets', 'icons'), 'assets/icons'), *_tess_data],
    hiddenimports=[
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'PySide6.QtSvg',
        'pytesseract', 'PIL._tkinter_finder',
        'pynput', 'pynput._util.darwin', 'pynput.keyboard._darwin',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MySnipaste',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(PROJECT_DIR, 'icon.icns')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MySnipaste',
)
app = BUNDLE(
    coll,
    name='MySnipaste.app',
    icon=os.path.join(PROJECT_DIR, 'icon.icns'),
    bundle_identifier='com.mysnipaste.app',
    info_plist={
        'NSScreenCaptureUsageDescription':
            'MySnipaste needs screen recording permission to capture screenshots.',
        'NSInputMonitoringUsageDescription':
            'MySnipaste needs input monitoring permission to detect global hotkeys.',
    },
)
