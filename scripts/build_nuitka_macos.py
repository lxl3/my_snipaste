#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
openSnipaste macOS Nuitka 构建脚本

用法:
    python scripts/build_nuitka_macos.py

先决条件:
    brew install tesseract tesseract-lang
    pip install nuitka
"""

import sys
import subprocess
import shutil
from pathlib import Path

from build_common import (
    BUILD_NAME,
    get_project_dir,
    print_step,
    find_tesseract,
    prepare_tesseract_bundle,
    patch_info_plist,
)

PROJECT_DIR = get_project_dir()
DIST_DIR = PROJECT_DIR / "dist"
NUITKA_OUTPUT = DIST_DIR / "nuitka-build"


def clean_build():
    print_step("清理旧构建文件")
    for p in [NUITKA_OUTPUT, DIST_DIR / f"{BUILD_NAME}.app"]:
        if p.exists():
            shutil.rmtree(p)
    DIST_DIR.mkdir(exist_ok=True)


def find_app() -> Path | None:
    for candidate in NUITKA_OUTPUT.rglob("*.app"):
        if (candidate / "Contents" / "MacOS" / BUILD_NAME).exists():
            return candidate
    return None


def build_and_package():
    print_step("准备 Tesseract OCR")
    tesseract_bin, _ = find_tesseract()
    prepare_tesseract_bundle(tesseract_bin, None, PROJECT_DIR / "build")

    tess_bundle_src = PROJECT_DIR / "build" / "tesseract_bundle"
    if tess_bundle_src.exists():
        subprocess.run(["xattr", "-cr", str(tess_bundle_src)], capture_output=True)

    include_data = [
        f"{PROJECT_DIR / 'assets' / 'icons'}=assets/icons",
        f"{PROJECT_DIR / 'src' / 'resources' / 'locales'}=resources/locales",
    ]
    if tess_bundle_src.exists():
        include_data.append(f"{tess_bundle_src}=tesseract")

    icon_path = PROJECT_DIR / "icon.icns"

    print_step("Nuitka 编译（app-dist 模式）")
    cmd = [
        sys.executable, "-m", "nuitka",
        "--mode=app-dist",
        f"--output-filename={BUILD_NAME}",
        f"--output-dir={NUITKA_OUTPUT}",
        "--enable-plugin=pyside6",
        "--include-package=src",
        "--include-package=pytesseract",
        "--include-package=PIL",
    ]
    if icon_path.exists():
        cmd.append(f"--macos-app-icon={icon_path}")

    for data_dir in include_data:
        cmd.append(f"--include-data-dir={data_dir}")

    cmd.append(str(PROJECT_DIR / "main.py"))

    print(f"\n执行命令:\n{' '.join(cmd)}\n")
    subprocess.run(cmd, cwd=PROJECT_DIR)

    built_app = find_app()
    if built_app is None:
        print("\n✗ 未找到生成的 .app")
        if NUITKA_OUTPUT.exists():
            for f in sorted(NUITKA_OUTPUT.rglob("*")):
                print(f"  {f.relative_to(NUITKA_OUTPUT)}")
        return False

    dest = DIST_DIR / f"{BUILD_NAME}.app"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(built_app, dest)

    print(f"\n✓ 应用已生成: {dest}")
    total_size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    print(f"✓ 应用大小: {total_size / (1024 * 1024):.1f} MB")

    if tesseract_bin:
        print("✓ Tesseract OCR: 已打包")
    else:
        print("⚠️ Tesseract OCR: 未打包")

    patch_info_plist(dest)

    print("  清理扩展属性并签名...")
    subprocess.run(["xattr", "-cr", str(dest)], capture_output=True)
    r = subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(dest)],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print("  ✓ 签名成功 (ad-hoc)")
    else:
        print(f"  ⚠️ 签名失败: {r.stderr.strip()}")

    return True


def main():
    print("=" * 60)
    print("  openSnipaste macOS Nuitka 构建工具")
    print("=" * 60)

    try:
        import nuitka  # noqa
    except ImportError:
        print("[ERROR] Nuitka 未安装，请运行: pip install nuitka")
        sys.exit(1)

    if shutil.which("clang") is None:
        print("[ERROR] 未找到 clang，请安装 Xcode CLI: xcode-select --install")
        sys.exit(1)

    clean_build()
    if not build_and_package():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  [OK] macOS Nuitka 构建完成")
    print("=" * 60)
    print(f"\n输出位置: {DIST_DIR / BUILD_NAME}.app")
    print("\n测试运行: open dist/openSnipaste.app")


if __name__ == "__main__":
    main()
