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
  <!-- 左矩形（x=3~11, y=2~11, w=8, h=9） -->
  <rect x="3" y="2" width="8" height="9" rx="1"/>
  <!-- 右矩形（x=13~21, y=2~11, w=8, h=9） -->
  <rect x="13" y="2" width="8" height="9" rx="1"/>
  <!-- 左下旗帜（x=3~11, y=13~20, 燕尾至 y=23） -->
  <path d="M3 13h8v7l-4 3l-4-3z"/>
  <!-- 右下旗帜（x=13~21, y=13~20, 燕尾至 y=23） -->
  <path d="M21 13h-8v7l4 3l4-3z"/>
</svg>"""


def draw_icon(size):
    """使用 PySide6 QSvgRenderer 渲染 SVG 图标

    策略：先将 SVG 渲染到 256×256 高分辨率画布上，
    再用 PIL 的 LANCZOS 重采样缩放到目标尺寸。

    Qt.SmoothTransformation（双线性插值）在大比例缩小时过于柔和，
    LANCZOS 能保留更多边缘锐度。

    Args:
        size: 目标图标尺寸

    Returns:
        PIL.Image: 生成的图标图像
    """
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtCore import Qt, QByteArray
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import QBuffer

    RENDER_SIZE = 256

    src = QImage(RENDER_SIZE, RENDER_SIZE, QImage.Format_ARGB32)
    src.fill(Qt.transparent)
    renderer = QSvgRenderer(QByteArray(SVG_CONTENT.encode('utf-8')))
    painter = QPainter(src)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    # QImage → PIL Image
    buffer = QBuffer()
    buffer.open(QBuffer.ReadWrite)
    src.save(buffer, 'PNG')
    buffer.seek(0)
    pil_img = Image.open(io.BytesIO(buffer.data().data())).convert('RGBA')

    # 用 PIL LANCZOS 缩放到目标尺寸（比 Qt.SmoothTransformation 更锐利）
    if pil_img.size != (size, size):
        pil_img = pil_img.resize((size, size), Image.LANCZOS)
    return pil_img


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
    """生成多尺寸 ICO 图标文件

    NOTE: Pillow 的 Image.save(format='ICO', append_images=...) 在多个版本中
    存在多帧写入损坏的 bug（https://github.com/python-pillow/Pillow/issues/5850）。
    这里手动构造 ICO 结构：将每个尺寸的 PNG 直接存入 ICO 的 ICONDIRENTRY 中。
    """
    import struct

    print("\n正在生成 ICO 图标...")

    images = [draw_icon(size) for size in SIZES]
    ico_path = PROJECT_DIR / "icon.ico"

    # 将每张 PNG 序列化为字节
    png_data_list = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        png_data_list.append(buf.getvalue())

    # ICO 文件格式：
    #   ICONDIR (6 bytes)
    #   ICONDIRENTRY[] (16 bytes each)
    #   Image data (PNG)
    count = len(images)
    header = struct.pack('<HHH', 0, 1, count)  # reserved, type=1(ico), count

    entries = []
    data_offset = 6 + count * 16  # 第一个图像数据的偏移量
    for i, png_data in enumerate(png_data_list):
        w = 256 if SIZES[i] == 256 else SIZES[i]  # 0 = 256
        entry = struct.pack(
            '<BBBBHHII',
            w & 0xFF,                 # width (0=256)
            SIZES[i] & 0xFF,          # height
            0,                        # colors
            0,                        # reserved
            1,                        # planes
            32,                       # bpp
            len(png_data),            # size
            data_offset,              # offset
        )
        entries.append(entry)
        data_offset += len(png_data)

    with open(ico_path, 'wb') as f:
        f.write(header)
        for entry in entries:
            f.write(entry)
        for png_data in png_data_list:
            f.write(png_data)

    total_size = sum(len(d) for d in png_data_list)
    print(f"  [OK] icon.ico (包含 {len(SIZES)} 种尺寸, {total_size:,} 字节 PNG 数据)")
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
