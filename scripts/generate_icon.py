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
from PIL import Image, ImageDraw

# 项目根目录
PROJECT_DIR = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_DIR / "assets" / "icons"

# 设计规格
COLORS = {
    'primary': '#FFFFFF',        # 白色线条
    'background': '#3498DB'      # 浅蓝色背景
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
        'padding': int(size * 0.15),           # 边距 15%
        'line_width': max(2, size // 16),      # 线条宽度
        'corner_radius': max(3, size // 12),   # 圆角半径
        'rect_size': int(size * 0.5),          # 矩形框大小
        'magnifier_radius': int(size * 0.2),   # 放大镜半径
        'handle_length': int(size * 0.15),     # 放大镜手柄长度
    }


def draw_icon(size):
    """绘制指定尺寸的图标（参考 doubao 风格：截图框+放大镜）

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
    line_width = dims['line_width']
    corner_radius = dims['corner_radius']

    # 绘制截图矩形框（左上角，带虚线效果的选区）
    rect_left = padding
    rect_top = padding
    rect_right = rect_left + dims['rect_size']
    rect_bottom = rect_top + dims['rect_size']

    # 绘制主矩形框
    draw.rounded_rectangle(
        [rect_left, rect_top, rect_right, rect_bottom],
        radius=corner_radius,
        outline=COLORS['primary'],
        width=line_width
    )

    # 绘制内部文本线条（表示内容）
    line_spacing = dims['rect_size'] // 5
    line_start_x = rect_left + line_width * 2
    line_end_x = rect_right - line_width * 2

    for i in range(3):
        y = rect_top + line_spacing * (i + 1)
        if y < rect_bottom - line_spacing:
            draw.line(
                [(line_start_x, y), (line_end_x, y)],
                fill=COLORS['primary'],
                width=max(1, line_width - 1)
            )

    # 绘制放大镜（右下角，象征 OCR/识别）
    mag_center_x = size - padding - dims['magnifier_radius']
    mag_center_y = size - padding - dims['magnifier_radius']
    mag_radius = dims['magnifier_radius']

    # 放大镜圆圈
    draw.ellipse(
        [mag_center_x - mag_radius, mag_center_y - mag_radius,
         mag_center_x + mag_radius, mag_center_y + mag_radius],
        outline=COLORS['primary'],
        width=line_width
    )

    # 放大镜手柄
    handle_start_x = mag_center_x + mag_radius * 0.7
    handle_start_y = mag_center_y + mag_radius * 0.7
    handle_end_x = handle_start_x + dims['handle_length']
    handle_end_y = handle_start_y + dims['handle_length']

    draw.line(
        [(handle_start_x, handle_start_y), (handle_end_x, handle_end_y)],
        fill=COLORS['primary'],
        width=line_width + 1
    )

    return img


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
