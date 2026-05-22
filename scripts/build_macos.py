#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySnipaste macOS 构建脚本
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


def build_app():
    """使用 PyInstaller 打包 macOS 应用"""
    print_step("开始打包 macOS 应用")

    # PyInstaller 命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", BUILD_NAME,
        "--windowed",  # macOS GUI 应用
        "--onefile",   # 单文件模式
        "--icon", str(PROJECT_DIR / "icon.icns") if (PROJECT_DIR / "icon.icns").exists() else str(PROJECT_DIR / "icon.ico"),

        # 添加数据文件
        "--add-data", f"{PROJECT_DIR / 'assets' / 'icons'}:assets/icons",

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
    ]

    print(f"执行命令: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True, cwd=PROJECT_DIR)
        print("\n[OK] 打包完成")

        # 检查输出
        app_path = DIST_DIR / f"{BUILD_NAME}.app"
        if app_path.exists():
            print(f"\n✓ 应用已生成: {app_path}")
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
    print("  MySnipaste macOS 构建工具")
    print("=" * 60)

    # 检查是否在 macOS 上
    if sys.platform != "darwin":
        print("[ERROR] 此脚本只能在 macOS 上运行")
        sys.exit(1)

    # 检查 Tesseract 是否安装
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✓ Tesseract 已安装: {result.stdout.split()[1]}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[ERROR] Tesseract 未安装，请运行: brew install tesseract tesseract-lang")
        sys.exit(1)

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


if __name__ == "__main__":
    main()
