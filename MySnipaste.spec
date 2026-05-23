# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/a60036901/Desktop/project/AI/my_snipaste/main.py'],
    pathex=[],
    binaries=[('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/tesseract', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libopenjp2.7.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libpng16.16.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libgif.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libwebp.7.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libtesseract.5.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libwebpmux.3.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/liblz4.1.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libarchive.13.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/liblzma.5.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libzstd.1.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libjpeg.8.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libleptonica.6.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libb2.1.dylib', 'tesseract'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/libtiff.6.dylib', 'tesseract')],
    datas=[('/Users/a60036901/Desktop/project/AI/my_snipaste/assets/icons', 'assets/icons'), ('/Users/a60036901/Desktop/project/AI/my_snipaste/build/tesseract_bundle/tessdata', 'tesseract/tessdata')],
    hiddenimports=['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'pytesseract', 'PIL._tkinter_finder', 'pynput', 'pynput._util.darwin', 'pynput.keyboard._darwin'],
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
    icon=['/Users/a60036901/Desktop/project/AI/my_snipaste/icon.icns'],
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
    icon='/Users/a60036901/Desktop/project/AI/my_snipaste/icon.icns',
    bundle_identifier='com.mysnipaste.app',
)
