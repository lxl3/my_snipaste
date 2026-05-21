#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySnipaste 构建脚本
自动下载 Tesseract 并打包成独立 exe。

用法:
    python build.py          # 完整构建（下载 tesseract + 打包）
    python build.py --skip-download  # 使用已有的 tesseract_bundle 打包
"""

import os
import sys
import subprocess
import shutil
import urllib.request
import tempfile
import zipfile
from pathlib import Path

# 项目根目录
PROJECT_DIR = Path(__file__).parent
BUNDLE_DIR = PROJECT_DIR / "tesseract_bundle"
DIST_DIR = PROJECT_DIR / "dist"
BUILD_NAME = "MySnipaste"

# Tesseract 下载配置
TESSERACT_VERSION = "5.5.0"
TESSERACT_BUILD = "20241111"
TESSERACT_URL = (
    f"https://github.com/tesseract-ocr/tesseract/releases/"
    f"download/{TESSERACT_VERSION}/"
    f"tesseract-ocr-w64-setup-{TESSERACT_VERSION}.{TESSERACT_BUILD}.exe"
)

# 语言数据下载 URL
LANG_DATA_URLS = {
    "eng.traineddata": "https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata",
    "chi_sim.traineddata": "https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata",
}


def print_step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def download_file(url, dest, desc="文件"):
    """下载文件并显示进度"""
    print(f"正在下载 {desc}...")
    print(f"URL: {url}")

    def progress_hook(count, block_size, total_size):
        if total_size > 0:
            percent = min(count * block_size * 100 / total_size, 100)
            bar_len = 40
            filled = int(bar_len * percent / 100)
            bar = '█' * filled + '░' * (bar_len - filled)
            print(f"\r  [{bar}] {percent:.1f}%", end='', flush=True)

    urllib.request.urlretrieve(url, dest, progress_hook)
    print()  # 换行


def setup_tesseract_bundle():
    """准备 tesseract_bundle 目录"""
    print_step("准备 Tesseract 运行文件")

    BUNDLE_DIR.mkdir(exist_ok=True)

    # 1. 下载语言数据
    tessdata_dir = BUNDLE_DIR / "tessdata"
    tessdata_dir.mkdir(exist_ok=True)

    for filename, url in LANG_DATA_URLS.items():
        dest = tessdata_dir / filename
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"  [OK] {filename} 已存在")
        else:
            download_file(url, str(dest), filename)
            print(f"  [OK] {filename} 下载完成")

    # 2. 检查 tesseract.exe 是否存在
    tesseract_exe = BUNDLE_DIR / "tesseract.exe"
    if tesseract_exe.exists():
        print(f"  [OK] tesseract.exe 已存在")
        return True

    # 3. 尝试从系统已安装的 Tesseract 复制
    system_paths = [
        r"C:\Program Files\Tesseract-OCR",
        r"C:\Program Files (x86)\Tesseract-OCR",
    ]
    for path in system_paths:
        src_exe = Path(path) / "tesseract.exe"
        if src_exe.exists():
            print(f"  从系统安装复制: {path}")
            copy_tesseract_files(Path(path), BUNDLE_DIR)
            return True

    # 4. 下载并提取安装程序
    print("\n  需要下载 Tesseract 可执行文件...")
    installer_path = PROJECT_DIR / "tesseract_setup.exe"

    if not installer_path.exists():
        download_file(TESSERACT_URL, str(installer_path), "Tesseract 安装程序")

    # 尝试静默安装到 bundle 目录
    print(f"\n  正在安装到 {BUNDLE_DIR}...")
    try:
        result = subprocess.run(
            [str(installer_path), '/VERYSILENT', '/SUPPRESSMSGBOXES',
             f'/DIR={BUNDLE_DIR}', '/NORESTART', '/NOICONS'],
            capture_output=True, timeout=120
        )
        if (BUNDLE_DIR / "tesseract.exe").exists():
            print("  [OK] Tesseract 安装成功")
            # 确保 tessdata 目录存在
            if not tessdata_dir.exists():
                tessdata_dir.mkdir(exist_ok=True)
            return True
    except Exception as e:
        print(f"  静默安装失败: {e}")

    # 5. 如果以上都失败，提示用户
    print("\n" + "!"*60)
    print("  无法自动获取 Tesseract 可执行文件")
    print("  请手动操作：")
    print("  1. 下载: https://github.com/tesseract-ocr/tesseract/releases")
    print(f"  2. 安装到: {BUNDLE_DIR}")
    print("  3. 重新运行此脚本")
    print("!"*60)
    return False


def copy_tesseract_files(src_dir, dest_dir):
    """从源目录复制 tesseract 相关文件到目标目录"""
    # 复制可执行文件
    for pattern in ["*.exe", "*.dll"]:
        for f in src_dir.glob(pattern):
            shutil.copy2(f, dest_dir / f.name)
            print(f"  复制: {f.name}")

    # 复制 tessdata
    src_tessdata = src_dir / "tessdata"
    if src_tessdata.exists():
        dest_tessdata = dest_dir / "tessdata"
        if dest_tessdata.exists():
            shutil.rmtree(dest_tessdata)
        shutil.copytree(src_tessdata, dest_tessdata)
        print(f"  复制: tessdata/")


def run_pyinstaller():
    """运行 PyInstaller 打包"""
    print_step("运行 PyInstaller 打包")

    # 构建 --add-binary 和 --add-data 参数
    add_data_args = []

    if BUNDLE_DIR.exists():
        # 添加 tesseract 可执行文件和 DLL
        for f in BUNDLE_DIR.iterdir():
            if f.is_file() and f.suffix in ['.exe', '.dll']:
                add_data_args.extend(['--add-binary', f'{f};tesseract'])

        # 添加 tessdata 目录
        tessdata_dir = BUNDLE_DIR / "tessdata"
        if tessdata_dir.exists():
            add_data_args.extend(['--add-data', f'{tessdata_dir};tesseract/tessdata'])

    # 构建 PyInstaller 命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name', BUILD_NAME,
        '--clean',
        '--noconfirm',
    ]
    cmd.extend(add_data_args)
    cmd.append(str(PROJECT_DIR / 'main.py'))

    print("执行命令:")
    print(' '.join(cmd))
    print()

    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))

    if result.returncode == 0:
        exe_path = DIST_DIR / f"{BUILD_NAME}.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print_step(f"打包成功！")
            print(f"  文件: {exe_path}")
            print(f"  大小: {size_mb:.1f} MB")
            return True

    print_step("打包失败")
    return False


def main():
    print("="*60)
    print("  MySnipaste 构建工具")
    print("="*60)

    skip_download = '--skip-download' in sys.argv

    if not skip_download:
        if not setup_tesseract_bundle():
            print("\n构建中止: 需要先准备 Tesseract 文件")
            print("运行 'python build.py --skip-download' 可跳过此步骤")
            sys.exit(1)
    else:
        print("\n[跳过下载] 使用已有的 tesseract_bundle 目录")
        if not (BUNDLE_DIR / "tesseract.exe").exists():
            print("警告: tesseract_bundle/tesseract.exe 不存在")
            print("打包后的 exe 将不包含 OCR 功能")

    if not run_pyinstaller():
        sys.exit(1)


if __name__ == "__main__":
    main()
