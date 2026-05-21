# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\project\\my_snipaste\\main.py'],
    pathex=[],
    binaries=[('D:\\project\\my_snipaste\\tesseract_bundle\\libarchive-13.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libb2-1.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libbrotlicommon.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libbrotlidec.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libbz2-1.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libcairo-2.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libcrypto-3-x64.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libcurl-4.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libdatrie-1.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libdeflate.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libexpat-1.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libffi-8.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libfontconfig-1.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libfreetype-6.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libfribidi-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libgcc_s_seh-1.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libgif-7.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libgio-2.0-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libglib-2.0-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libgmodule-2.0-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libgobject-2.0-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libgraphite2.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libharfbuzz-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libiconv-2.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libicudt75.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libicuin75.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libicuuc75.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libidn2-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libintl-8.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libjbig-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libjpeg-8.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libleptonica-6.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libLerc.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\liblz4.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\liblzma-5.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libopenjp2-7.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libpango-1.0-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libpangocairo-1.0-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libpangoft2-1.0-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libpangowin32-1.0-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libpcre2-8-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libpixman-1-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libpng16-16.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libpsl-5.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libsharpyuv-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libssh2-1.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libstdc++-6.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libtesseract-5.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libthai-0.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libtiff-6.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libunistring-5.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libwebp-7.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libwebpmux-3.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libwinpthread-1.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\libzstd.dll', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\tesseract.exe', 'tesseract'), ('D:\\project\\my_snipaste\\tesseract_bundle\\zlib1.dll', 'tesseract')],
    datas=[('D:\\project\\my_snipaste\\tesseract_bundle\\tessdata', 'tesseract/tessdata')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MySnipaste',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
