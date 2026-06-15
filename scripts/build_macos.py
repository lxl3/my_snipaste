#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySnipaste macOS 构建脚本（PyInstaller，支持 Tesseract OCR 打包）
"""

import os
import sys
import subprocess
from pathlib import Path

from build_common import (
    BUILD_NAME,
    PYINSTALLER_HIDDEN_IMPORTS,
    PYINSTALLER_EXCLUDES,
    get_project_dir,
    print_step,
    clean_build,
    find_tesseract,
    prepare_tesseract_bundle,
    patch_info_plist,
    prune_app,
    sign_app,
    create_icns,
)

PROJECT_DIR = get_project_dir()
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"


def build_app() -> bool:
    print_step("开始打包 macOS 应用")

    tesseract_bin, tessdata_dir = find_tesseract()
    tess_bin_paths, tess_data_paths = prepare_tesseract_bundle(
        tesseract_bin, tessdata_dir, BUILD_DIR
    )

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", BUILD_NAME,
        "--windowed",
        "--onedir",
        "--osx-bundle-identifier", "com.mysnipaste.app",
    ]

    icon = PROJECT_DIR / "icon.icns"
    if icon.exists():
        cmd.extend(["--icon", str(icon)])
    elif (PROJECT_DIR / "icon.ico").exists():
        cmd.extend(["--icon", str(PROJECT_DIR / "icon.ico")])

    cmd.extend(["--add-data", f"{PROJECT_DIR / 'assets' / 'icons'}:assets/icons"])
    cmd.extend(["--add-data", f"{PROJECT_DIR / 'src' / 'resources' / 'locales'}:resources/locales"])

    for p in tess_bin_paths:
        cmd.extend(["--add-binary", f"{Path(p)}:tesseract"])
    for p in tess_data_paths:
        cmd.extend(["--add-data", f"{p}:tesseract/tessdata"])

    for mod in PYINSTALLER_HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", mod])
    for mod in PYINSTALLER_EXCLUDES:
        cmd.extend(["--exclude-module", mod])

    cmd.append(str(PROJECT_DIR / "main.py"))

    print(f"\n执行命令:\n{' '.join(cmd)}\n")

    try:
        subprocess.run(cmd, check=True, cwd=PROJECT_DIR)
        app_path = DIST_DIR / f"{BUILD_NAME}.app"
        if app_path.exists():
            total_size = sum(f.stat().st_size for f in app_path.rglob("*") if f.is_file())
            print(f"\n  路径: {app_path}")
            print(f"  大小: {total_size / (1024 * 1024):.1f} MB")
            if tesseract_bin:
                print("  Tesseract OCR: 已打包")
            prune_app(app_path)
            patch_info_plist(app_path)
            sign_app(app_path)
            return True
        print(f"\n  未找到: {app_path}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] 打包失败: {e}")
        return False


def main() -> None:
    print("=" * 60)
    print("  MySnipaste macOS 构建工具（PyInstaller）")
    print("=" * 60)

    if sys.platform != "darwin":
        print("[WARN] 此脚本设计用于 macOS")

    create_icns(PROJECT_DIR)
    clean_build(DIST_DIR, BUILD_DIR, PROJECT_DIR)

    if not build_app():
        sys.exit(1)

    print(f"\n输出: {DIST_DIR / BUILD_NAME}.app")
    print("运行: open dist/MySnipaste.app")


if __name__ == "__main__":
    main()
