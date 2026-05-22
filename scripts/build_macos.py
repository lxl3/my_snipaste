#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySnipaste macOS 构建脚本（支持 Tesseract OCR 打包）
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# 项目根目录
PROJECT_DIR = Path(__file__).parent.parent
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"
BUILD_NAME = "MySnipaste"


def print_step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def clean_build():
    """清理旧的构建文件"""
    print_step("清理旧构建文件")

    for dir_path in [DIST_DIR, BUILD_DIR]:
        if dir_path.exists():
            print(f"删除: {dir_path}")
            shutil.rmtree(dir_path)

    # 清理 spec 文件
    spec_files = list(PROJECT_DIR.glob("*.spec"))
    for spec_file in spec_files:
        print(f"删除: {spec_file}")
        spec_file.unlink()

    print("[OK] 清理完成")


def find_tesseract():
    """查找 Tesseract 二进制文件和数据目录

    Returns:
        tuple: (tesseract_bin, tessdata_dir) 或 (None, None)
    """
    print_step("查找 Tesseract OCR 引擎")

    # 可能的 Tesseract 路径（Homebrew Intel 和 Apple Silicon）
    tesseract_paths = [
        "/opt/homebrew/bin/tesseract",  # Apple Silicon (M1/M2)
        "/usr/local/bin/tesseract",     # Intel
    ]

    tessdata_paths = [
        "/opt/homebrew/share/tessdata",
        "/usr/local/share/tessdata",
    ]

    # 查找 Tesseract 二进制
    tesseract_bin = None
    for path in tesseract_paths:
        if Path(path).exists():
            tesseract_bin = path
            print(f"✓ 找到 Tesseract: {tesseract_bin}")
            break

    if not tesseract_bin:
        print("⚠️ Tesseract 未安装")
        return None, None

    # 查找 tessdata 目录
    tessdata_dir = None
    for path in tessdata_paths:
        if Path(path).exists():
            tessdata_dir = path
            print(f"✓ 找到语言包目录: {tessdata_dir}")
            break

    if not tessdata_dir:
        print("⚠️ Tesseract 语言包未找到")
        return tesseract_bin, None

    # 检查必需的语言包
    required_langs = ["eng", "chi_sim"]
    missing_langs = []
    for lang in required_langs:
        lang_file = Path(tessdata_dir) / f"{lang}.traineddata"
        if lang_file.exists():
            print(f"  - {lang}: ✓")
        else:
            print(f"  - {lang}: ✗ 缺失")
            missing_langs.append(lang)

    if missing_langs:
        print(f"\n⚠️ 缺少语言包: {', '.join(missing_langs)}")
        print("   请运行: brew install tesseract-lang")

    return tesseract_bin, tessdata_dir


def prepare_tesseract_bundle(tesseract_bin, tessdata_dir):
    """准备 Tesseract 打包目录

    Args:
        tesseract_bin: Tesseract 二进制文件路径
        tessdata_dir: Tesseract 语言包目录

    Returns:
        tuple: (binary_args, data_args) 用于 PyInstaller 参数
    """
    if not tesseract_bin or not tessdata_dir:
        print("⚠️ 跳过 Tesseract 打包")
        return [], []

    print_step("准备 Tesseract 打包")

    # 创建临时打包目录
    temp_tess_dir = BUILD_DIR / "tesseract_bundle"
    temp_tess_dir.mkdir(parents=True, exist_ok=True)

    # 复制 Tesseract 二进制
    temp_tess_bin = temp_tess_dir / "tesseract"
    shutil.copy2(tesseract_bin, temp_tess_bin)
    # 确保可执行
    os.chmod(temp_tess_bin, 0o755)
    print(f"✓ 已复制 Tesseract 二进制")

    # 复制语言包（只复制需要的，减小体积）
    temp_tessdata = temp_tess_dir / "tessdata"
    temp_tessdata.mkdir(exist_ok=True)

    required_langs = ["eng", "chi_sim"]
    total_size = 0
    for lang in required_langs:
        lang_file = f"{lang}.traineddata"
        src = Path(tessdata_dir) / lang_file
        dst = temp_tessdata / lang_file

        if src.exists():
            shutil.copy2(src, dst)
            size_mb = src.stat().st_size / (1024 * 1024)
            total_size += size_mb
            print(f"  - {lang}: {size_mb:.1f} MB")

    print(f"✓ 语言包总大小: {total_size:.1f} MB")

    # 返回 PyInstaller 参数
    binary_args = [
        "--add-binary", f"{temp_tess_bin}:tesseract",
    ]

    data_args = [
        "--add-data", f"{temp_tessdata}:tesseract/tessdata",
    ]

    return binary_args, data_args


def build_app():
    """使用 PyInstaller 打包 macOS 应用"""
    print_step("开始打包 macOS 应用")

    # 查找 Tesseract
    tesseract_bin, tessdata_dir = find_tesseract()

    # 准备 Tesseract 打包
    tess_binary_args, tess_data_args = prepare_tesseract_bundle(tesseract_bin, tessdata_dir)

    # PyInstaller 基础命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", BUILD_NAME,
        "--windowed",  # macOS GUI 应用
        "--onefile",   # 单文件模式
        "--icon", str(PROJECT_DIR / "icon.icns") if (PROJECT_DIR / "icon.icns").exists() else str(PROJECT_DIR / "icon.ico"),

        # 添加数据文件
        "--add-data", f"{PROJECT_DIR / 'assets' / 'icons'}:assets/icons",
    ]

    # 添加 Tesseract 文件（如果找到）
    cmd.extend(tess_binary_args)
    cmd.extend(tess_data_args)

    # 隐藏导入和排除模块
    cmd.extend([
        # 隐藏导入
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "PySide6.QtWidgets",
        "--hidden-import", "pytesseract",
        "--hidden-import", "PIL._tkinter_finder",

        # 排除不需要的模块
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",

        # 入口文件
        str(PROJECT_DIR / "main.py"),
    ])

    print(f"\n执行命令:\n{' '.join(cmd)}\n")

    try:
        subprocess.run(cmd, check=True, cwd=PROJECT_DIR)
        print("\n[OK] 打包完成")

        # 检查输出
        app_path = DIST_DIR / f"{BUILD_NAME}.app"
        if app_path.exists():
            # 计算 .app 大小
            total_size = sum(f.stat().st_size for f in app_path.rglob('*') if f.is_file())
            size_mb = total_size / (1024 * 1024)

            print(f"\n✓ 应用已生成: {app_path}")
            print(f"✓ 应用大小: {size_mb:.1f} MB")

            if tesseract_bin:
                print(f"✓ Tesseract OCR: 已打包（开箱即用）")
            else:
                print(f"⚠️ Tesseract OCR: 未打包（需要用户安装）")

            return True
        else:
            print(f"\n✗ 应用未找到: {app_path}")
            return False

    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] 打包失败: {e}")
        return False


def create_icns():
    """如果不存在 .icns 文件，从 PNG 创建"""
    icns_path = PROJECT_DIR / "icon.icns"
    if icns_path.exists():
        return

    print_step("创建 .icns 图标")

    png_path = PROJECT_DIR / "assets" / "icons" / "icon-256.png"
    if not png_path.exists():
        print("[WARN] 未找到 icon-256.png，跳过 .icns 创建")
        return

    # 使用 sips 和 iconutil（macOS 自带）创建 .icns
    iconset_path = PROJECT_DIR / "icon.iconset"
    iconset_path.mkdir(exist_ok=True)

    sizes = [16, 32, 128, 256, 512]
    for size in sizes:
        for scale in [1, 2]:
            actual_size = size * scale
            suffix = f"@{scale}x" if scale == 2 else ""
            output = iconset_path / f"icon_{size}x{size}{suffix}.png"

            # 查找合适的源文件
            source = PROJECT_DIR / "assets" / "icons" / f"icon-{actual_size}.png"
            if not source.exists():
                source = png_path

            subprocess.run([
                "sips", "-z", str(actual_size), str(actual_size),
                str(source), "--out", str(output)
            ], check=True, capture_output=True)

    # 转换为 .icns
    subprocess.run([
        "iconutil", "-c", "icns", str(iconset_path),
        "-o", str(icns_path)
    ], check=True)

    shutil.rmtree(iconset_path)
    print(f"[OK] 已创建: {icns_path}")


def main():
    """主函数"""
    print("=" * 60)
    print("  MySnipaste macOS 构建工具（支持 Tesseract 打包）")
    print("=" * 60)

    # 检查是否在 macOS 上
    if sys.platform != "darwin":
        print("[WARN] 此脚本设计用于 macOS，但可以在其他平台上修改")
        print("       实际构建将在 GitHub Actions 的 macOS 服务器上进行")

    # 构建流程
    create_icns()
    clean_build()

    if not build_app():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  [OK] macOS 应用构建完成")
    print("=" * 60)
    print(f"\n输出位置: {DIST_DIR / BUILD_NAME}.app")
    print("\n测试运行: open dist/MySnipaste.app")
    print("\n提示：")
    print("  - 如果 Tesseract 已打包，用户无需额外安装")
    print("  - 如果 Tesseract 未打包，用户需运行: brew install tesseract tesseract-lang")


if __name__ == "__main__":
    main()
