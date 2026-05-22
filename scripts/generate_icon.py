#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySnipaste 图标生成脚本

根据 SVG 设计生成多尺寸应用图标：
- 透明背景
- 白色填充 + 黑色描边
- 支持 16x16 到 256x256 多种尺寸
"""

import sys
from pathlib import Path
from PIL import Image
import io

# 项目根目录
PROJECT_DIR = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_DIR / "assets" / "icons"

# 支持的尺寸
SIZES = [16, 32, 48, 128, 256]

# SVG 图标设计
SVG_CONTENT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#ffffff" stroke="#333333" stroke-width="0.3">
  <!-- 左上矩形 -->
  <rect x="5" y="4" width="6" height="7" rx="1"/>
  <!-- 右上矩形 -->
  <rect x="13" y="4" width="6" height="7" rx="1"/>
  <!-- 左下旗帜（燕尾尖角） -->
  <path d="M5 13h6v7l-3 3l-3-3z"/>
  <!-- 右下旗帜（燕尾尖角） -->
  <path d="M19 13h-6v7l3 3l3-3z"/>
</svg>"""


def draw_icon(size):
    """使用 PySide6 QSvgRenderer 渲染 SVG 图标

    Args:
        size: 图标尺寸

    Returns:
        PIL.Image: 生成的图标图像
    """
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtCore import Qt, QByteArray
    from PySide6.QtSvg import QSvgRenderer

    # 创建透明 QImage
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)

    # 渲染 SVG
    renderer = QSvgRenderer(QByteArray(SVG_CONTENT.encode('utf-8')))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    # 转换为 PIL Image
    from PySide6.QtCore import QBuffer
    buffer = QBuffer()
    buffer.open(QBuffer.ReadWrite)
    img.save(buffer, 'PNG')
    buffer.seek(0)
    return Image.open(io.BytesIO(buffer.data().data())).convert('RGBA')


def generate_png_icons():
    """生成所有尺寸的 PNG 图标"""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    print("正在生成 PNG 图标...")
    for size in SIZES:
        img = draw_icon(size)
        output_path = ASSETS_DIR / f"icon-{size}.png"
        img.save(output_path, 'PNG')
        print(f"  [OK] {output_path.name}")

    return True


def generate_ico_icon():
    """生成多尺寸 ICO 图标文件"""
    print("\n正在生成 ICO 图标...")

    # 生成所有尺寸的图像
    images = [draw_icon(size) for size in SIZES]

    # 保存为 ICO（包含所有尺寸）
    ico_path = PROJECT_DIR / "icon.ico"
    images[0].save(
        ico_path,
        format='ICO',
        sizes=[(img.width, img.height) for img in images],
        append_images=images[1:]
    )

    print(f"  [OK] icon.ico (包含 {len(SIZES)} 种尺寸)")
    return True


def main():
    """主函数"""
    print("=" * 60)
    print("  MySnipaste 图标生成工具")
    print("=" * 60)

    # 生成 PNG
    if not generate_png_icons():
        print("\n[ERROR] PNG 图标生成失败")
        sys.exit(1)

    # 生成 ICO
    if not generate_ico_icon():
        print("\n[ERROR] ICO 图标生成失败")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  [OK] 所有图标生成完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
