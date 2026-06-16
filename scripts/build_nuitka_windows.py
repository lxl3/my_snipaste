#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
openSnipaste Windows Nuitka 构建脚本

用法:
    python scripts/build_nuitka_windows.py

先决条件:
    pip install nuitka
    需要 C 编译器 (MSVC 或 MinGW)
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

from build_common import (
    BUILD_NAME,
    get_project_dir,
    print_step,
)

PROJECT_DIR = get_project_dir()
DIST_DIR = PROJECT_DIR / "dist"
NUITKA_OUTPUT = DIST_DIR / "nuitka-build"
BUNDLE_DIR = PROJECT_DIR / "tesseract_bundle"


def clean_build():
    print_step("清理旧构建文件")
    for p in [NUITKA_OUTPUT, DIST_DIR / f"{BUILD_NAME}.exe"]:
        if p.exists():
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            except PermissionError:
                print(f"  [跳过] {p.name} 被占用，无法删除")
    DIST_DIR.mkdir(exist_ok=True)


def build_and_package():
    print_step("准备数据文件")

    include_data = [
        f"{PROJECT_DIR / 'assets' / 'icons'}=assets/icons",
        f"{PROJECT_DIR / 'src' / 'resources' / 'locales'}=resources/locales",
    ]

    include_binary = []
    if BUNDLE_DIR.exists():
        include_data.append(f"{BUNDLE_DIR / 'tessdata'}=tesseract/tessdata")
        for f in BUNDLE_DIR.iterdir():
            if f.is_file() and f.suffix in (".exe", ".dll"):
                include_binary.append(f"{f}=tesseract/")

    icon_path = PROJECT_DIR / "icon.ico"

    print_step("Nuitka 编译")
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        f"--output-dir={NUITKA_OUTPUT}",
        "--enable-plugin=pyside6",
        "--include-package=src",
        "--include-package=pytesseract",
        "--include-package=PIL",
        "--windows-console-mode=disable",
        "--assume-yes-for-downloads",
        "--show-progress",
        f"--jobs={os.cpu_count() or 4}",
        "--msvc=latest",
    ]

    if icon_path.exists():
        cmd.append(f"--windows-icon-from-ico={icon_path}")

    for data_dir in include_data:
        cmd.append(f"--include-data-dir={data_dir}")

    for binary in include_binary:
        cmd.append(f"--include-data-files={binary}")

    cmd.append(str(PROJECT_DIR / "main.py"))

    print(f"\n执行命令:\n{' '.join(cmd)}\n")
    sys.stdout.flush()

    process = subprocess.Popen(
        cmd, cwd=PROJECT_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in process.stdout:
        print(line, end="", flush=True)
    returncode = process.wait()

    if returncode != 0:
        print("\n[FAIL] Nuitka 编译失败")
        return False

    # Derive output exe path from entry-point filename (main.py → main.exe)
    entry_stem = Path("main.py").stem  # "main"
    built_exe = NUITKA_OUTPUT / f"{entry_stem}.dist" / f"{entry_stem}.exe"
    if not built_exe.exists():
        for candidate in NUITKA_OUTPUT.rglob("*.exe"):
            if candidate.name in (f"{entry_stem}.exe", f"{BUILD_NAME}.exe"):
                built_exe = candidate
                break

    if not built_exe.exists():
        print(f"\n[FAIL] 未找到生成的 exe")
        if NUITKA_OUTPUT.exists():
            contents = sorted(NUITKA_OUTPUT.rglob("*"))
            for f in contents[:20]:
                print(f"  {f.relative_to(NUITKA_OUTPUT)}")
        return False

    dest = DIST_DIR / f"{BUILD_NAME}.exe"
    if dest.exists():
        dest.unlink()
    shutil.copy2(built_exe, dest)

    print(f"\n[OK] 应用已生成: {dest}")
    size = dest.stat().st_size / (1024 * 1024)
    print(f"[OK] 应用大小: {size:.1f} MB")

    if BUNDLE_DIR.exists():
        print("[OK] Tesseract OCR: 已打包")
    else:
        print("[WARN] Tesseract OCR: 未打包")

    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="openSnipaste Windows Nuitka 构建工具")
    parser.add_argument(
        "--clean", "-c", action="store_true",
        help="清理旧构建文件，强制从零编译（默认：增量编译，更快）",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  openSnipaste Windows Nuitka 构建工具")
    print("=" * 60)

    if sys.platform != "win32":
        print("[WARN] 此脚本设计用于 Windows")

    try:
        import nuitka  # noqa
    except ImportError:
        print("[ERROR] Nuitka 未安装，请运行: pip install nuitka")
        sys.exit(1)

    if args.clean:
        clean_build()
    else:
        print_step("增量编译（保留缓存，加快速度）")
        print("  提示: 如需从零编译请加 --clean 参数\n")
        DIST_DIR.mkdir(exist_ok=True)

    if not build_and_package():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  [OK] Windows Nuitka 构建完成")
    print("=" * 60)
    print(f"\n输出位置: {DIST_DIR / BUILD_NAME}.exe")


if __name__ == "__main__":
    main()
