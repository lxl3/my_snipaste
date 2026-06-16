#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
openSnipaste Windows 构建脚本（PyInstaller，自动下载 Tesseract）

用法:
    python scripts/build_windows.py
    python scripts/build_windows.py --skip-download
"""

import os
import sys
import subprocess
import shutil
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from build_common import (
    BUILD_NAME,
    PYINSTALLER_EXCLUDES,
    print_step,
    clean_build,
    check_source_changed,
    get_project_dir,
)

PROJECT_DIR = get_project_dir()
BUNDLE_DIR = PROJECT_DIR / "tesseract_bundle"
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"

TESSERACT_VERSION = "5.5.0"
TESSERACT_BUILD = "20241111"
TESSERACT_URL = (
    f"https://github.com/tesseract-ocr/tesseract/releases/"
    f"download/{TESSERACT_VERSION}/"
    f"tesseract-ocr-w64-setup-{TESSERACT_VERSION}.{TESSERACT_BUILD}.exe"
)
LANG_DATA_URLS = {
    "eng.traineddata": "https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata",
    "chi_sim.traineddata": "https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata",
}


def download_file(url: str, dest: str, desc: str = "文件") -> bool:
    if Path(dest).exists() and Path(dest).stat().st_size > 1000:
        print(f"  [跳过] {desc} 已存在")
        return True

    print(f"正在下载 {desc}...")

    def progress(count, block_size, total_size):
        if total_size > 0:
            pct = min(count * block_size * 100 / total_size, 100)
            bar = int(40 * pct / 100)
            print(f"\r  [{'█' * bar}{'░' * (40 - bar)}] {pct:.1f}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, dest, progress)
        print()
        return True
    except Exception as e:
        print(f"\n  [错误] 下载失败: {e}")
        return False


def download_lang_files_parallel() -> bool:
    tessdata_dir = BUNDLE_DIR / "tessdata"
    tessdata_dir.mkdir(exist_ok=True)

    def download_one(item):
        filename, url = item
        return download_file(url, str(tessdata_dir / filename), filename)

    with ThreadPoolExecutor(max_workers=2) as executor:
        return all(executor.map(download_one, LANG_DATA_URLS.items()))


def setup_tesseract_bundle() -> bool:
    """Download/extract Tesseract for Windows into tesseract_bundle."""
    print_step("准备 Tesseract 运行文件")
    BUNDLE_DIR.mkdir(exist_ok=True)

    print("下载语言数据...")
    download_lang_files_parallel()

    tesseract_exe = BUNDLE_DIR / "tesseract.exe"
    if tesseract_exe.exists():
        print("  tesseract.exe 已存在")
        return True

    system_paths = [
        r"C:\Program Files\Tesseract-OCR",
        r"C:\Program Files (x86)\Tesseract-OCR",
    ]
    for path in system_paths:
        src_exe = Path(path) / "tesseract.exe"
        if src_exe.exists():
            print(f"从系统安装复制: {path}")
            for pattern in ["*.exe", "*.dll"]:
                for f in Path(path).glob(pattern):
                    shutil.copy2(f, BUNDLE_DIR / f.name)
            src_tessdata = Path(path) / "tessdata"
            if src_tessdata.exists():
                dst = BUNDLE_DIR / "tessdata"
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src_tessdata, dst)
            return True

    print("\n下载 Tesseract 安装程序...")
    installer = PROJECT_DIR / "tesseract_setup.exe"
    download_file(TESSERACT_URL, str(installer), "Tesseract 安装程序")

    try:
        subprocess.run(
            [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES",
             f"/DIR={BUNDLE_DIR}", "/NORESTART", "/NOICONS"],
            capture_output=True, timeout=120,
        )
        if tesseract_exe.exists():
            (BUNDLE_DIR / "tessdata").mkdir(exist_ok=True)
            installer.unlink(missing_ok=True)
            return True
    except Exception as e:
        print(f"静默安装失败: {e}")

    print("\n无法获取 Tesseract，请手动下载安装到:", BUNDLE_DIR)
    return False


def run_pyinstaller(use_spec=True, force_rebuild=False, onedir=False) -> bool:
    print_step("运行 PyInstaller 打包")

    is_windows = sys.platform == "win32"

    if not force_rebuild and use_spec:
        spec_file = PROJECT_DIR / f"{BUILD_NAME}.spec"
        if spec_file.exists() and DIST_DIR.exists() and not check_source_changed(PROJECT_DIR):
            print("  [跳过] 源文件未变化")
            exe_path = DIST_DIR / (f"{BUILD_NAME}.exe" if is_windows else f"{BUILD_NAME}.app")
            if exe_path.exists():
                size = sum(f.stat().st_size for f in exe_path.rglob("*") if f.is_file()) / (1024 * 1024)
                print(f"  文件: {exe_path}")
                print(f"  大小: {size:.1f} MB")
                return True

    if use_spec:
        spec_file = PROJECT_DIR / f"{BUILD_NAME}.spec"
        if spec_file.exists():
            print(f"使用 spec 文件: {spec_file}")
            cmd = [sys.executable, "-m", "PyInstaller"]
            if force_rebuild:
                cmd.append("--clean")
            cmd.extend(["--noconfirm", str(spec_file)])
        else:
            use_spec = False

    if not use_spec:
        add_data_args = []
        if BUNDLE_DIR.exists():
            for f in BUNDLE_DIR.iterdir():
                if f.is_file() and f.suffix in (".exe", ".dll"):
                    add_data_args.extend(["--add-binary", f"{f};tesseract"])
            tessdata = BUNDLE_DIR / "tessdata"
            if tessdata.exists():
                add_data_args.extend(["--add-data", f"{tessdata};tesseract/tessdata"])

        assets_icons = PROJECT_DIR / "assets" / "icons"
        if assets_icons.exists():
            add_data_args.extend(["--add-data", f"{assets_icons};assets/icons"])

        locales_dir = PROJECT_DIR / "src" / "resources" / "locales"
        if locales_dir.exists():
            add_data_args.extend(["--add-data", f"{locales_dir};resources/locales"])

        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onedir" if onedir else "--onefile",
            "--windowed",
            "--name", BUILD_NAME,
            "--noconfirm",
        ]
        if force_rebuild:
            cmd.append("--clean")

        icon = PROJECT_DIR / ("icon.ico" if is_windows else "icon.icns")
        if icon.exists():
            cmd.extend(["--icon", str(icon)])

        for mod in PYINSTALLER_EXCLUDES:
            cmd.extend(["--exclude-module", mod])

        cmd.extend(add_data_args)
        cmd.append(str(PROJECT_DIR / "main.py"))

    print("执行:\n" + " ".join(cmd) + "\n")

    if subprocess.run(cmd, cwd=str(PROJECT_DIR)).returncode != 0:
        print_step("打包失败")
        return False

    exe_path = DIST_DIR / f"{BUILD_NAME}.exe"
    if exe_path.exists():
        size = exe_path.stat().st_size / (1024 * 1024)
        print_step("打包成功！")
        print(f"  文件: {exe_path}")
        print(f"  大小: {size:.1f} MB")
        return True

    print_step("打包失败")
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="openSnipaste Windows 构建工具")
    parser.add_argument("--skip-download", action="store_true", help="跳过 Tesseract 下载")
    parser.add_argument("--force-rebuild", action="store_true", help="强制重新构建")
    parser.add_argument("--no-spec", action="store_true", help="不使用 spec 文件")
    parser.add_argument("--onedir", action="store_true", help="使用 --onedir 模式")
    args = parser.parse_args()

    if sys.platform == "win32":
        if not args.skip_download and not setup_tesseract_bundle():
            sys.exit(1)
    else:
        print("[macOS/其他] 跳过 Windows Tesseract 设置")

    if not run_pyinstaller(
        use_spec=not args.no_spec,
        force_rebuild=args.force_rebuild,
        onedir=args.onedir,
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()
