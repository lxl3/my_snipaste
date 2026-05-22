#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySnipaste 构建脚本
自动下载 Tesseract 并打包成独立 exe。

用法:
    python scripts/build_windows.py          # 完整构建（下载 tesseract + 打包）
    python scripts/build_windows.py --skip-download  # 使用已有的 tesseract_bundle 打包
"""

import os
import sys
import subprocess
import shutil
import urllib.request
import tempfile
import zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import platform

# 项目根目录
PROJECT_DIR = Path(__file__).resolve().parent.parent
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
    # 检查文件是否已存在且有效
    if Path(dest).exists() and Path(dest).stat().st_size > 1000:
        print(f"  [跳过] {desc} 已存在")
        return True

    print(f"正在下载 {desc}...")
    print(f"URL: {url}")

    def progress_hook(count, block_size, total_size):
        if total_size > 0:
            percent = min(count * block_size * 100 / total_size, 100)
            bar_len = 40
            filled = int(bar_len * percent / 100)
            bar = '█' * filled + '░' * (bar_len - filled)
            print(f"\r  [{bar}] {percent:.1f}%", end='', flush=True)

    try:
        urllib.request.urlretrieve(url, dest, progress_hook)
        print()  # 换行
        return True
    except Exception as e:
        print(f"\n  [错误] 下载失败: {e}")
        return False


def download_lang_files_parallel():
    """并行下载语言文件"""
    tessdata_dir = BUNDLE_DIR / "tessdata"
    tessdata_dir.mkdir(exist_ok=True)

    def download_one(item):
        filename, url = item
        dest = tessdata_dir / filename
        return download_file(url, str(dest), filename)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(download_one, LANG_DATA_URLS.items()))

    return all(results)


def setup_tesseract_bundle():
    """准备 tesseract_bundle 目录"""
    print_step("准备 Tesseract 运行文件")

    BUNDLE_DIR.mkdir(exist_ok=True)

    # 1. 并行下载语言数据
    print("正在检查/下载语言数据...")
    if not download_lang_files_parallel():
        print("  [警告] 部分语言文件下载失败")

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


def check_source_changed():
    """检查源文件是否有变化（简单的增量构建检测）"""
    cache_file = PROJECT_DIR / "build" / ".build_cache"
    src_files = list(PROJECT_DIR.glob("src/**/*.py")) + [PROJECT_DIR / "main.py"]

    if not src_files:
        return True  # 如果找不到源文件，强制重新构建

    # 计算所有源文件的最新修改时间
    latest_mtime = max(f.stat().st_mtime for f in src_files if f.exists())

    if cache_file.exists():
        try:
            cached_mtime = float(cache_file.read_text().strip())
            if latest_mtime <= cached_mtime:
                return False  # 没有变化
        except:
            pass

    # 保存当前时间戳
    cache_file.parent.mkdir(exist_ok=True)
    cache_file.write_text(str(latest_mtime))
    return True


def run_pyinstaller(use_spec=True, force_rebuild=False, onedir=False):
    """运行 PyInstaller 打包

    Args:
        use_spec: 使用 .spec 文件（更快）
        force_rebuild: 强制重新构建（清除缓存）
        onedir: 使用 --onedir 模式（更快，但生成文件夹）
    """
    print_step("运行 PyInstaller 打包")

    # 判断操作系统（在函数开始就定义，避免后续使用时未定义）
    is_windows = platform.system() == "Windows"

    # 增量构建检测
    if not force_rebuild and use_spec:
        spec_file = PROJECT_DIR / f"{BUILD_NAME}.spec"
        if spec_file.exists() and DIST_DIR.exists():
            if not check_source_changed():
                print("  [跳过] 源文件未变化，使用已有的构建结果")
                is_windows = platform.system() == "Windows"
                exe_path = DIST_DIR / (f"{BUILD_NAME}.exe" if is_windows else f"{BUILD_NAME}.app")
                if exe_path.exists():
                    size_mb = sum(
                        f.stat().st_size for f in exe_path.rglob("*") if f.is_file()
                    ) / (1024 * 1024) if not is_windows else exe_path.stat().st_size / (1024 * 1024)
                    print(f"  文件: {exe_path}")
                    print(f"  大小: {size_mb:.1f} MB")
                    return True

    if use_spec:
        spec_file = PROJECT_DIR / f"{BUILD_NAME}.spec"
        if spec_file.exists():
            spec_content = spec_file.read_text()
            is_windows_spec = ":\\" in spec_content or ".dll" in spec_content or ".exe" in spec_content
            is_current_windows = platform.system() == "Windows"

            if is_windows_spec and not is_current_windows:
                print("  [警告] spec 文件包含 Windows 路径，正在重新生成...")
                use_spec = False
            else:
                print(f"使用 spec 文件: {spec_file}")
                cmd = [sys.executable, '-m', 'PyInstaller']
                if not force_rebuild:
                    print("  [优化] 保留构建缓存（增量构建）")
                else:
                    cmd.append('--clean')
                cmd.extend(['--noconfirm', str(spec_file)])
        else:
            print("  [警告] spec 文件不存在，使用命令行模式")
            use_spec = False

    if not use_spec:
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

        # 添加图标资源
        assets_icons = PROJECT_DIR / "assets" / "icons"
        if assets_icons.exists():
            add_data_args.extend(['--add-data', f'{assets_icons};assets/icons'])

        # 构建 PyInstaller 命令
        mode_arg = '--onedir' if onedir else '--onefile'
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            mode_arg,
            '--windowed',
            '--name', BUILD_NAME,
            '--noconfirm',
        ]

        icon_file = PROJECT_DIR / "icon.icns" if not is_windows else PROJECT_DIR / "icon.ico"
        if icon_file.exists():
            cmd.extend(['--icon', str(icon_file)])
        if not force_rebuild:
            print("  [优化] 保留构建缓存（增量构建）")
        else:
            cmd.append('--clean')

        cmd.extend(add_data_args)
        cmd.append(str(PROJECT_DIR / 'main.py'))

    print("执行命令:")
    print(' '.join(cmd))
    print()

    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))

    if result.returncode == 0:
        is_windows = platform.system() == "Windows"
        if is_windows:
            exe_path = DIST_DIR / f"{BUILD_NAME}.exe"
        else:
            exe_path = DIST_DIR / f"{BUILD_NAME}.app"

        if exe_path.exists():
            if is_windows:
                size_mb = exe_path.stat().st_size / (1024 * 1024)
                print_step(f"打包成功！")
                print(f"  文件: {exe_path}")
                print(f"  大小: {size_mb:.1f} MB")
            else:
                size_mb = sum(
                    f.stat().st_size for f in exe_path.rglob("*") if f.is_file()
                ) / (1024 * 1024)
                print_step(f"打包成功！")
                print(f"  文件: {exe_path}")
                print(f"  大小: {size_mb:.1f} MB")
            return True

    print_step("打包失败")
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MySnipaste 构建工具（优化版）")
    parser.add_argument('--skip-download', action='store_true',
                        help='跳过 Tesseract 下载，使用已有文件')
    parser.add_argument('--force-rebuild', action='store_true',
                        help='强制重新构建（清除缓存）')
    parser.add_argument('--no-spec', action='store_true',
                        help='不使用 spec 文件，直接用命令行参数')
    parser.add_argument('--onedir', action='store_true',
                        help='使用 --onedir 模式（更快，生成文件夹）')
    args = parser.parse_args()

    print("="*60)
    print("  MySnipaste 构建工具（优化版）")
    print("="*60)
    print("\n优化特性:")
    print("  ✓ 并行下载语言文件")
    print("  ✓ 智能缓存检测（增量构建）")
    print("  ✓ 保留 PyInstaller 缓存")
    if not args.force_rebuild:
        print("  ✓ 跳过未修改的源文件")
    print()

    is_windows = platform.system() == "Windows"

    if is_windows:
        if not args.skip_download:
            if not setup_tesseract_bundle():
                print("\n构建中止: 需要先准备 Tesseract 文件")
                print("运行 'python scripts/build_windows.py --skip-download' 可跳过此步骤")
                sys.exit(1)
        else:
            print("\n[跳过下载] 使用已有的 tesseract_bundle 目录")
            if not (BUNDLE_DIR / "tesseract.exe").exists():
                print("警告: tesseract_bundle/tesseract.exe 不存在")
                print("打包后的 exe 将不包含 OCR 功能")
    else:
        print("\n[macOS] 跳过 Windows Tesseract 设置")
        print("如需 OCR 功能，请通过 Homebrew 安装: brew install tesseract")

    if not run_pyinstaller(
        use_spec=not args.no_spec,
        force_rebuild=args.force_rebuild,
        onedir=args.onedir
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()
