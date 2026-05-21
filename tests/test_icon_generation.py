#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""图标生成脚本测试"""

import sys
from pathlib import Path
from PIL import Image

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.generate_icon import (
    calculate_dimensions,
    draw_icon,
    SIZES,
    PROJECT_DIR,
    ASSETS_DIR
)


def test_calculate_dimensions():
    """测试尺寸计算"""
    print("测试 calculate_dimensions...")

    # 测试 256x256
    dims = calculate_dimensions(256)
    assert 'padding' in dims
    assert 'line_width' in dims
    assert 'corner_radius' in dims
    assert dims['padding'] > 0
    assert dims['line_width'] >= 2

    # 测试 16x16（最小尺寸）
    dims = calculate_dimensions(16)
    assert dims['padding'] > 0
    assert dims['line_width'] >= 2
    assert dims['corner_radius'] >= 2

    print("  [OK] 尺寸计算正确")


def test_draw_icon():
    """测试图标绘制"""
    print("\n测试 draw_icon...")

    for size in SIZES:
        img = draw_icon(size)

        # 检查图像属性
        assert img.size == (size, size), f"图标尺寸不匹配: {img.size} != ({size}, {size})"
        assert img.mode == 'RGBA', f"图像模式应为 RGBA，实际为 {img.mode}"

        # 检查不是全透明（应该有内容）
        pixels = list(img.getdata())
        non_transparent = [p for p in pixels if p[3] > 0]
        assert len(non_transparent) > 0, f"{size}x{size} 图标是全透明的"

        print(f"  [OK] {size}x{size} 图标正常")


def test_icon_files_exist():
    """测试图标文件是否生成"""
    print("\n测试图标文件...")

    # 检查 PNG 文件
    for size in SIZES:
        png_path = ASSETS_DIR / f"icon-{size}.png"
        if png_path.exists():
            img = Image.open(png_path)
            assert img.size == (size, size), f"{png_path.name} 尺寸不正确"
            print(f"  [OK] {png_path.name} 存在且正确")
        else:
            print(f"  [WARN] {png_path.name} 不存在（运行 generate_icon.py 生成）")

    # 检查 ICO 文件
    ico_path = PROJECT_DIR / "icon.ico"
    if ico_path.exists():
        print(f"  [OK] icon.ico 存在")
    else:
        print(f"  [WARN] icon.ico 不存在（运行 generate_icon.py 生成）")


def test_icon_in_build():
    """测试图标是否正确集成到构建中"""
    print("\n测试构建集成...")

    # 检查 spec 文件
    spec_path = PROJECT_DIR / "MySnipaste.spec"
    if spec_path.exists():
        content = spec_path.read_text(encoding='utf-8')
        assert "icon='icon.ico'" in content or 'icon="icon.ico"' in content, \
            "spec 文件中未找到 icon 参数"
        print("  [OK] MySnipaste.spec 包含 icon 参数")

    # 检查 build.py
    build_path = PROJECT_DIR / "build.py"
    if build_path.exists():
        content = build_path.read_text(encoding='utf-8')
        assert "--icon" in content or "'--icon'" in content, \
            "build.py 中未找到 --icon 参数"
        print("  [OK] build.py 包含 --icon 参数")

    print("  [OK] 构建配置正确")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("  图标生成测试")
    print("=" * 60)

    try:
        test_calculate_dimensions()
        test_draw_icon()
        test_icon_files_exist()
        test_icon_in_build()  # 添加集成测试

        print("\n" + "=" * 60)
        print("  [OK] 所有测试通过")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n[ERROR] 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] 测试错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
