#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySnipaste 图标生成脚本

根据设计规格生成多尺寸应用图标：
- 圆角矩形框（截图功能）
- 字母 'A'（OCR 功能）
- 深灰色系配色
- 支持 16x16 到 256x256 多种尺寸
"""

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# 项目根目录
PROJECT_DIR = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_DIR / "assets" / "icons"

# 设计规格
COLORS = {
    'frame': '#2C3E50',      # 深灰色框线
    'text': '#ECF0F1',       # 浅灰白色文字
    'background': (0, 0, 0, 0)  # 透明背景
}

# 支持的尺寸
SIZES = [16, 32, 48, 128, 256]


def calculate_dimensions(size):
    """计算给定尺寸的图标各元素尺寸

    Args:
        size: 图标尺寸（正方形边长）

    Returns:
        dict: 包含各元素尺寸的字典
    """
    return {
        'padding': int(size * 0.11),           # 边距 11%
        'border_width': max(2, size // 32),    # 框线宽度
        'corner_radius': max(2, size // 11),   # 圆角半径
        'letter_height': int(size * 0.47),     # 字母高度
    }


def draw_icon(size):
    """绘制指定尺寸的图标

    Args:
        size: 图标尺寸

    Returns:
        PIL.Image: 生成的图标图像
    """
    # 创建透明画布
    img = Image.new('RGBA', (size, size), COLORS['background'])
    draw = ImageDraw.Draw(img)

    # 计算尺寸
    dims = calculate_dimensions(size)
    padding = dims['padding']
    border_width = dims['border_width']
    corner_radius = dims['corner_radius']

    # 绘制圆角矩形框
    box_coords = [padding, padding, size - padding, size - padding]
    draw.rounded_rectangle(
        box_coords,
        radius=corner_radius,
        outline=COLORS['frame'],
        width=border_width
    )

    # 绘制字母 'A'
    draw_letter_a(draw, size, dims)

    return img


def draw_letter_a(draw, size, dims):
    """在图标中央绘制字母 'A'

    Args:
        draw: ImageDraw 对象
        size: 图标尺寸
        dims: 尺寸参数字典
    """
    letter_height = dims['letter_height']

    # 尝试加载系统字体
    font = get_font(letter_height)

    # 计算文字位置（居中）
    text = 'A'
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (size - text_width) // 2
    y = (size - text_height) // 2 - bbox[1]

    # 绘制文字
    draw.text((x, y), text, fill=COLORS['text'], font=font)


def get_font(size):
    """获取合适的字体

    Args:
        size: 字体大小

    Returns:
        ImageFont: 字体对象
    """
    # 尝试常见的无衬线字体
    font_names = [
        'arial.ttf',
        'Arial.ttf',
        'helvetica.ttf',
        'DejaVuSans.ttf',
        'LiberationSans-Regular.ttf',
    ]

    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue

    # 如果都找不到，使用默认字体
    return ImageFont.load_default()


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
