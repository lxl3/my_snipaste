# 应用图标实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 openSnipaste 创建并集成应用图标（圆角框+字母A，深灰色系，多尺寸支持）

**Architecture:** 使用 Python/Pillow 生成矢量图标，支持多尺寸（16-256px），导出为 ICO 和 PNG 格式，集成到 PyInstaller 构建流程和系统托盘显示

**Tech Stack:** Python 3.12+, Pillow (图像生成), PyInstaller (打包), PySide6 (系统托盘)

---

## 文件结构

### 新建文件
- `scripts/generate_icon.py` - 图标生成脚本（核心逻辑）
- `icon.ico` - 多尺寸 ICO 图标文件
- `assets/icons/icon-16.png` - 16x16 PNG
- `assets/icons/icon-32.png` - 32x32 PNG
- `assets/icons/icon-48.png` - 48x48 PNG
- `assets/icons/icon-128.png` - 128x128 PNG
- `assets/icons/icon-256.png` - 256x256 PNG
- `tests/test_icon_generation.py` - 图标生成测试

### 修改文件
- `openSnipaste.spec` - 添加 icon 参数
- `build.py` - 添加 --icon 参数
- `src/app.py` - 加载系统托盘图标

---

## Task 1: 创建图标生成脚本基础结构

**Files:**
- Create: `scripts/generate_icon.py`
- Create: `tests/test_icon_generation.py`

- [ ] **Step 1: 创建图标生成脚本文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
openSnipaste 图标生成脚本

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
        print(f"  ✓ {output_path.name}")
    
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
    
    print(f"  ✓ icon.ico (包含 {len(SIZES)} 种尺寸)")
    return True


def main():
    """主函数"""
    print("=" * 60)
    print("  openSnipaste 图标生成工具")
    print("=" * 60)
    
    # 生成 PNG
    if not generate_png_icons():
        print("\n❌ PNG 图标生成失败")
        sys.exit(1)
    
    # 生成 ICO
    if not generate_ico_icon():
        print("\n❌ ICO 图标生成失败")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("  ✓ 所有图标生成完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 创建测试文件**

```python
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
    get_font,
    SIZES,
    PROJECT_DIR,
    ASSETS_DIR
)


def test_calculate_dimensions():
    """测试尺寸计算"""
    print("测试 calculate_dimensions...")
    
    # 测试 256x256
    dims = calculate_dimensions(256)
    assert dims['padding'] == 28, f"期望 padding=28, 实际={dims['padding']}"
    assert dims['border_width'] == 8, f"期望 border_width=8, 实际={dims['border_width']}"
    assert dims['corner_radius'] == 23, f"期望 corner_radius=23, 实际={dims['corner_radius']}"
    assert dims['letter_height'] == 120, f"期望 letter_height=120, 实际={dims['letter_height']}"
    
    # 测试 16x16（最小尺寸）
    dims = calculate_dimensions(16)
    assert dims['padding'] == 1
    assert dims['border_width'] >= 2  # 最小 2px
    assert dims['corner_radius'] >= 2  # 最小 2px
    
    print("  ✓ 尺寸计算正确")


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
        
        print(f"  ✓ {size}x{size} 图标正常")


def test_get_font():
    """测试字体加载"""
    print("\n测试 get_font...")
    
    font = get_font(120)
    assert font is not None, "字体加载失败"
    
    print("  ✓ 字体加载成功")


def test_icon_files_exist():
    """测试图标文件是否生成"""
    print("\n测试图标文件...")
    
    # 检查 PNG 文件
    for size in SIZES:
        png_path = ASSETS_DIR / f"icon-{size}.png"
        if png_path.exists():
            img = Image.open(png_path)
            assert img.size == (size, size), f"{png_path.name} 尺寸不正确"
            print(f"  ✓ {png_path.name} 存在且正确")
        else:
            print(f"  ⚠ {png_path.name} 不存在（运行 generate_icon.py 生成）")
    
    # 检查 ICO 文件
    ico_path = PROJECT_DIR / "icon.ico"
    if ico_path.exists():
        print(f"  ✓ icon.ico 存在")
    else:
        print(f"  ⚠ icon.ico 不存在（运行 generate_icon.py 生成）")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("  图标生成测试")
    print("=" * 60)
    
    try:
        test_calculate_dimensions()
        test_draw_icon()
        test_get_font()
        test_icon_files_exist()
        
        print("\n" + "=" * 60)
        print("  ✓ 所有测试通过")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 测试错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 运行测试验证代码结构**

```bash
python tests/test_icon_generation.py
```

期望输出：
```
============================================================
  图标生成测试
============================================================
测试 calculate_dimensions...
  ✓ 尺寸计算正确

测试 draw_icon...
  ✓ 16x16 图标正常
  ✓ 32x32 图标正常
  ✓ 48x48 图标正常
  ✓ 128x128 图标正常
  ✓ 256x256 图标正常

测试 get_font...
  ✓ 字体加载成功

测试图标文件...
  ⚠ icon-16.png 不存在（运行 generate_icon.py 生成）
  ... (其他尺寸同样)
  ⚠ icon.ico 不存在（运行 generate_icon.py 生成）

============================================================
  ✓ 所有测试通过
============================================================
```

- [ ] **Step 4: Commit**

```bash
git add scripts/generate_icon.py tests/test_icon_generation.py
git commit -m "feat: 添加图标生成脚本基础结构

- 实现图标绘制逻辑（圆角框 + 字母 A）
- 支持多尺寸生成（16-256px）
- 添加完整的单元测试
- 深灰色系配色方案

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 2: 生成图标文件

**Files:**
- Run: `scripts/generate_icon.py`
- Create: `icon.ico`
- Create: `assets/icons/icon-*.png` (5 个文件)

- [ ] **Step 1: 创建 assets/icons 目录**

```bash
mkdir -p assets/icons
```

- [ ] **Step 2: 运行图标生成脚本**

```bash
python scripts/generate_icon.py
```

期望输出：
```
============================================================
  openSnipaste 图标生成工具
============================================================
正在生成 PNG 图标...
  ✓ icon-16.png
  ✓ icon-32.png
  ✓ icon-48.png
  ✓ icon-128.png
  ✓ icon-256.png

正在生成 ICO 图标...
  ✓ icon.ico (包含 5 种尺寸)

============================================================
  ✓ 所有图标生成完成
============================================================
```

- [ ] **Step 3: 验证生成的文件**

```bash
ls -lh icon.ico assets/icons/
```

期望看到：
- `icon.ico` (约 50-100 KB)
- `assets/icons/icon-16.png` (约 1 KB)
- `assets/icons/icon-32.png` (约 2 KB)
- `assets/icons/icon-48.png` (约 3 KB)
- `assets/icons/icon-128.png` (约 8 KB)
- `assets/icons/icon-256.png` (约 15 KB)

- [ ] **Step 4: 再次运行测试确认文件正确**

```bash
python tests/test_icon_generation.py
```

期望输出现在所有图标文件都显示为 ✓ 存在且正确

- [ ] **Step 5: 在 Windows 上查看图标效果（可选验证）**

```bash
# 使用 Windows 默认图片查看器打开
explorer assets\icons\icon-256.png

# 或查看 ICO 文件属性
explorer icon.ico
```

手动验证：
- [ ] 圆角矩形框清晰可见
- [ ] 字母 'A' 居中且清晰
- [ ] 配色为深灰色系
- [ ] 各尺寸缩放合理

- [ ] **Step 6: Commit**

```bash
git add icon.ico assets/
git commit -m "feat: 生成应用图标文件

- 生成 ICO 文件（包含 5 种尺寸）
- 生成独立 PNG 文件（16-256px）
- 圆角框 + 字母 A 设计
- 深灰色系专业配色

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 3: 集成图标到 PyInstaller 构建

**Files:**
- Modify: `openSnipaste.spec:29`
- Modify: `build.py:183`

- [ ] **Step 1: 读取当前 spec 文件**

```bash
cat openSnipaste.spec | grep -A 5 "exe = EXE"
```

确认当前没有 icon 参数

- [ ] **Step 2: 修改 openSnipaste.spec 添加 icon 参数**

在 `openSnipaste.spec` 的 `exe = EXE(...)` 部分，在 `console=False,` 之后添加 `icon` 参数：

```python
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='openSnipaste',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 禁用 UPX 大幅提升打包速度（牺牲 ~20% 文件大小）
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='icon.ico',  # 添加应用图标
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

- [ ] **Step 3: 修改 build.py 添加 --icon 参数**

在 `build.py` 的 `run_pyinstaller` 函数中，找到命令行模式的命令构建部分（约 183 行附近），在 `'--windowed',` 之后添加 icon 参数：

```python
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

    # 构建 PyInstaller 命令
    mode_arg = '--onedir' if onedir else '--onefile'
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        mode_arg,
        '--windowed',
        '--icon', 'icon.ico',  # 添加图标参数
        '--name', BUILD_NAME,
        '--noconfirm',
    ]
    if not force_rebuild:
        print("  [优化] 保留构建缓存（增量构建）")
    else:
        cmd.append('--clean')

    cmd.extend(add_data_args)
    cmd.append(str(PROJECT_DIR / 'main.py'))
```

- [ ] **Step 4: 验证修改**

```bash
# 查看 spec 文件修改
git diff openSnipaste.spec

# 查看 build.py 修改
git diff build.py
```

确认两处都添加了图标参数

- [ ] **Step 5: Commit**

```bash
git add openSnipaste.spec build.py
git commit -m "feat: 集成图标到 PyInstaller 构建流程

- openSnipaste.spec: 添加 icon='icon.ico' 参数
- build.py: 命令行模式添加 --icon 参数
- 打包后的 exe 将显示自定义图标

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 4: 更新系统托盘图标

**Files:**
- Modify: `src/app.py`
- Test manually: 运行应用查看托盘图标

- [ ] **Step 1: 读取当前 app.py 中的托盘图标代码**

```bash
grep -n "QSystemTrayIcon\|setIcon\|tray" src/app.py | head -20
```

找到当前托盘图标的设置位置

- [ ] **Step 2: 在 app.py 中添加图标加载函数**

在 `SnipasteApp` 类的开头，添加图标加载方法：

```python
def load_app_icon(self):
    """加载应用图标（用于系统托盘）
    
    Returns:
        QIcon: 应用图标对象
    """
    from PySide6.QtGui import QIcon
    from pathlib import Path
    import sys
    
    # 确定图标路径
    if getattr(sys, 'frozen', False):
        # 打包后的路径
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境路径
        base_path = Path(__file__).parent.parent
    
    # 尝试加载 PNG 图标（系统托盘推荐）
    icon_sizes = [256, 128, 48, 32, 16]
    icon = QIcon()
    
    for size in icon_sizes:
        icon_path = base_path / "assets" / "icons" / f"icon-{size}.png"
        if icon_path.exists():
            icon.addFile(str(icon_path))
    
    # 如果 PNG 都不存在，尝试 ICO
    if icon.isNull():
        ico_path = base_path / "icon.ico"
        if ico_path.exists():
            icon = QIcon(str(ico_path))
    
    return icon
```

- [ ] **Step 3: 修改托盘图标设置代码**

找到 `SnipasteApp.__init__` 方法中创建系统托盘的代码，替换图标设置：

修改前（示例，具体代码可能不同）：
```python
self.tray_icon = QSystemTrayIcon(self)
self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
```

修改后：
```python
self.tray_icon = QSystemTrayIcon(self)
app_icon = self.load_app_icon()
if not app_icon.isNull():
    self.tray_icon.setIcon(app_icon)
else:
    # 如果图标加载失败，使用系统默认图标
    self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
```

- [ ] **Step 4: 同时设置应用窗口图标（如果需要）**

在 `__init__` 方法中添加：

```python
# 设置应用图标（用于窗口标题栏等）
app_icon = self.load_app_icon()
if not app_icon.isNull():
    self.setWindowIcon(app_icon)
```

- [ ] **Step 5: 更新 build.py 确保 PNG 图标被打包**

在 `build.py` 的 `run_pyinstaller` 函数中，添加 assets 目录到 --add-data：

```python
# 在添加 tesseract 数据之后添加
# 添加图标资源
assets_icons = PROJECT_DIR / "assets" / "icons"
if assets_icons.exists():
    add_data_args.extend(['--add-data', f'{assets_icons};assets/icons'])
```

注意：spec 文件也需要类似修改，在 `datas` 列表中添加：

```python
datas=[
    ('D:\\project\\my_snipaste\\tesseract_bundle\\tessdata', 'tesseract/tessdata'),
    ('D:\\project\\my_snipaste\\assets\\icons', 'assets/icons'),  # 添加此行
],
```

- [ ] **Step 6: 验证修改**

```bash
git diff src/app.py
git diff build.py
git diff openSnipaste.spec
```

- [ ] **Step 7: Commit**

```bash
git add src/app.py build.py openSnipaste.spec
git commit -m "feat: 更新系统托盘使用自定义图标

- 添加 load_app_icon() 方法加载图标
- 支持打包和开发环境两种路径
- 优先使用 PNG，回退到 ICO
- 更新构建脚本打包图标资源

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 5: 测试验证

**Files:**
- Test: 构建并运行应用

- [ ] **Step 1: 测试开发环境图标显示**

```bash
python main.py
```

验证清单：
- [ ] 应用启动成功
- [ ] 系统托盘显示自定义图标（深灰色圆角框+A）
- [ ] 图标清晰可辨识
- [ ] 没有错误日志

- [ ] **Step 2: 执行完整构建测试**

```bash
python build.py --skip-download
```

期望输出包含：
```
============================================================
  运行 PyInstaller 打包
============================================================
执行命令:
... --icon icon.ico ...
```

确认命令中包含 `--icon icon.ico` 参数

- [ ] **Step 3: 验证打包后的 exe 图标**

```bash
# 在 Windows 资源管理器中查看
explorer dist

# 右键 openSnipaste.exe -> 属性，查看图标
```

验证清单：
- [ ] exe 文件显示自定义图标（不是默认 Python 图标）
- [ ] 图标是深灰色圆角框+字母A
- [ ] 创建快捷方式后图标正确

- [ ] **Step 4: 运行打包后的应用测试托盘图标**

```bash
dist\openSnipaste.exe
```

验证清单：
- [ ] 应用正常启动
- [ ] 系统托盘显示自定义图标
- [ ] 图标与 exe 文件图标一致
- [ ] 所有功能正常（截图、OCR 等）

- [ ] **Step 5: 测试不同尺寸显示效果**

在 Windows 上测试：
- [ ] 大图标视图（256x256）- 快捷方式
- [ ] 任务栏图标（48x48）
- [ ] 系统托盘图标（16x16）
- [ ] Alt+Tab 切换窗口显示

确认所有尺寸都清晰可辨

- [ ] **Step 6: 更新测试脚本添加集成测试**

在 `tests/test_icon_generation.py` 末尾添加：

```python
def test_icon_in_build():
    """测试图标是否正确集成到构建中"""
    print("\n测试构建集成...")
    
    # 检查 spec 文件
    spec_path = PROJECT_DIR / "openSnipaste.spec"
    if spec_path.exists():
        content = spec_path.read_text(encoding='utf-8')
        assert "icon='icon.ico'" in content or 'icon="icon.ico"' in content, \
            "spec 文件中未找到 icon 参数"
        print("  ✓ openSnipaste.spec 包含 icon 参数")
    
    # 检查 build.py
    build_path = PROJECT_DIR / "build.py"
    if build_path.exists():
        content = build_path.read_text(encoding='utf-8')
        assert "--icon" in content or "'--icon'" in content, \
            "build.py 中未找到 --icon 参数"
        print("  ✓ build.py 包含 --icon 参数")
    
    print("  ✓ 构建配置正确")
```

在 `main()` 函数中添加调用：

```python
def main():
    """运行所有测试"""
    print("=" * 60)
    print("  图标生成测试")
    print("=" * 60)
    
    try:
        test_calculate_dimensions()
        test_draw_icon()
        test_get_font()
        test_icon_files_exist()
        test_icon_in_build()  # 添加此行
        
        print("\n" + "=" * 60)
        print("  ✓ 所有测试通过")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 测试错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
```

- [ ] **Step 7: 运行更新后的测试**

```bash
python tests/test_icon_generation.py
```

期望输出包含：
```
测试构建集成...
  ✓ openSnipaste.spec 包含 icon 参数
  ✓ build.py 包含 --icon 参数
  ✓ 构建配置正确
```

- [ ] **Step 8: Commit**

```bash
git add tests/test_icon_generation.py
git commit -m "test: 添加图标集成测试

- 验证 spec 和 build.py 配置
- 确保图标正确集成到构建流程

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 6: 文档更新

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 README.md 中添加图标说明**

在 "项目结构" 部分添加图标相关文件：

```markdown
## 项目结构

```
my_snipaste/
├── main.py              # 入口文件
├── build.py             # 构建脚本（自动下载 Tesseract 并打包）
├── icon.ico             # 应用图标（多尺寸）
├── requirements.txt     # Python 依赖
├── assets/
│   └── icons/           # 图标资源
│       ├── icon-16.png
│       ├── icon-32.png
│       ├── icon-48.png
│       ├── icon-128.png
│       └── icon-256.png
├── scripts/
│   └── generate_icon.py # 图标生成脚本
├── src/
│   ├── __init__.py      # 包初始化，版本定义
│   ├── app.py           # 主应用：托盘、快捷键、贴图窗口
│   ├── overlay.py       # 截图覆盖层：选区、标注工具栏
│   ├── editor.py        # 截图编辑器：高级标注、撤销/重做
│   ├── ocr_engine.py    # OCR 引擎：Tesseract 集成、异步识别
│   ├── utils.py         # 工具函数：截图、图像格式转换
│   └── resources/
│       └── icons/       # SVG 工具栏图标
└── tesseract_bundle/    # Tesseract 打包文件（构建用）
    ├── tesseract.exe
    ├── *.dll
    └── tessdata/
        ├── eng.traineddata
        └── chi_sim.traineddata
```
```

- [ ] **Step 2: 添加图标设计说明章节（可选）**

在 README.md 末尾或合适位置添加：

```markdown
## 应用图标

openSnipaste 使用自定义设计的应用图标：

**设计元素：**
- 🔲 圆角矩形框 - 象征截图选区
- 🅰️ 字母 'A' - 代表 OCR 文字识别
- 🎨 深灰色系 - 专业工具定位

**技术特性：**
- 支持多尺寸（16x16 到 256x256）
- 扁平化设计，清晰易辨识
- 使用 Python/Pillow 生成

**重新生成图标：**
```bash
python scripts/generate_icon.py
```

详细设计规格见 [图标设计文档](docs/superpowers/specs/2026-05-21-icon-design.md)。
```

- [ ] **Step 3: 验证 README 修改**

```bash
git diff README.md
```

确认添加的内容格式正确

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: 更新 README 添加图标说明

- 项目结构中添加图标文件
- 添加图标设计说明章节
- 链接到详细设计文档

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 7: 最终清理和发布准备

**Files:**
- Review: 所有修改的文件
- Test: 完整的构建和功能测试

- [ ] **Step 1: 检查所有修改**

```bash
git log --oneline -10
```

确认所有相关提交都已完成

- [ ] **Step 2: 完整构建测试**

```bash
# 清理旧的构建文件
rm -rf build/ dist/

# 完整构建
python build.py --skip-download --force-rebuild
```

验证构建成功且图标正确

- [ ] **Step 3: 功能回归测试**

运行打包后的应用，测试所有主要功能：
- [ ] F12 启动截图
- [ ] 截图选区和标注
- [ ] 保存截图
- [ ] 贴图功能
- [ ] OCR 文字识别
- [ ] 系统托盘菜单
- [ ] 图标在各处显示正确

- [ ] **Step 4: 检查文件大小**

```bash
ls -lh icon.ico assets/icons/*.png
ls -lh dist/openSnipaste.exe
```

确认：
- ICO 文件约 50-100 KB
- PNG 文件总计约 30 KB
- exe 文件大小合理（图标不应显著增加体积）

- [ ] **Step 5: 添加 .gitignore 条目（如果需要）**

确保 `.gitignore` 不会忽略图标文件：

```bash
# 检查 .gitignore
cat .gitignore | grep -i icon

# 如果图标被忽略，从 .gitignore 中移除相关规则
# 或者添加例外：
# !icon.ico
# !assets/icons/
```

- [ ] **Step 6: 创建发布标签（可选）**

```bash
git tag -a v0.1.0-icon -m "添加自定义应用图标

- 圆角框 + 字母 A 设计
- 深灰色系专业配色
- 多尺寸支持（16-256px）
- 完整集成到构建流程"

# 推送标签（如果需要）
# git push origin v0.1.0-icon
```

- [ ] **Step 7: 最终文档检查**

确认以下文档都是最新的：
- [ ] README.md - 包含图标说明
- [ ] docs/superpowers/specs/2026-05-21-icon-design.md - 设计文档
- [ ] docs/superpowers/plans/2026-05-21-icon-implementation.md - 实施计划
- [ ] BUILD_OPTIMIZATION.md - 如需更新（图标可能略微影响构建时间）

- [ ] **Step 8: 最终提交（如果有任何遗漏的修改）**

```bash
# 检查是否有未提交的修改
git status

# 如果有，提交
git add .
git commit -m "chore: 图标实现最终清理

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## 完成检查清单

全部任务完成后，验证以下所有项目：

### 文件生成
- [ ] `icon.ico` 存在且包含 5 种尺寸
- [ ] `assets/icons/` 目录包含 5 个 PNG 文件
- [ ] `scripts/generate_icon.py` 可独立运行
- [ ] `tests/test_icon_generation.py` 所有测试通过

### 集成验证
- [ ] `openSnipaste.spec` 包含 `icon='icon.ico'`
- [ ] `build.py` 包含 `--icon` 参数
- [ ] `src/app.py` 加载并使用自定义图标
- [ ] 图标资源被正确打包到 exe 中

### 功能验证
- [ ] 开发环境运行时托盘图标正确
- [ ] 打包后 exe 文件显示自定义图标
- [ ] 打包后运行时托盘图标正确
- [ ] 所有功能正常工作（截图、OCR 等）

### 文档验证
- [ ] README.md 包含图标说明
- [ ] 设计文档完整且准确
- [ ] 实施计划已执行完成
- [ ] 所有代码已提交到 git

### 视觉验证
- [ ] 图标设计符合规格（圆角框 + 字母 A）
- [ ] 配色正确（深灰色 #2C3E50）
- [ ] 各尺寸显示清晰
- [ ] 浅色/深色背景都能清晰识别

---

## 故障排查

### 问题：图标生成时字体不清晰

**症状**：字母 'A' 显示模糊或锯齿严重

**解决方案**：
1. 确保 Pillow 版本 >= 9.0
2. 尝试不同字体：
   ```python
   # 在 get_font() 中添加更多字体选项
   font_names = [
       'arialbd.ttf',  # Arial Bold
       'calibrib.ttf',  # Calibri Bold
       ...
   ]
   ```
3. 增加字体粗细（使用 Bold 或 Black 字重）

### 问题：系统托盘图标不显示

**症状**：托盘显示默认图标或空白

**解决方案**：
1. 检查 PNG 文件是否被正确打包：
   ```bash
   # 解压 exe 查看
   pyinstaller openSnipaste.spec --debug
   ```
2. 检查路径是否正确（开发环境 vs 打包环境）
3. 降级使用 ICO 文件：
   ```python
   icon = QIcon(str(PROJECT_DIR / "icon.ico"))
   ```

### 问题：打包后 exe 图标是默认 Python 图标

**症状**：exe 文件没有显示自定义图标

**解决方案**：
1. 确认 `icon.ico` 在项目根目录
2. 重新构建时使用 `--force-rebuild`：
   ```bash
   python build.py --skip-download --force-rebuild
   ```
3. 检查 spec 文件中 icon 路径是否正确
4. Windows 可能缓存图标，尝试：
   - 删除 `dist/` 目录
   - 重新构建
   - 刷新桌面或重启资源管理器

### 问题：16x16 尺寸下图标不清晰

**症状**：小尺寸托盘图标模糊

**解决方案**：
1. 调整 16x16 的设计：
   ```python
   if size == 16:
       # 使用更粗的线条
       border_width = 3
       # 简化字母 'A' 或改为实心圆点
   ```
2. 手工优化 16x16 PNG 文件
3. 使用专门设计的小尺寸图标

---

## 后续优化建议

完成基本实现后，可以考虑以下优化：

1. **动画托盘图标**：截图时托盘图标闪烁或变色
2. **多套图标**：亮色主题和暗色主题使用不同图标
3. **状态指示**：托盘图标显示应用状态（空闲/截图中/OCR中）
4. **macOS 图标**：创建 .icns 格式支持 macOS
5. **Linux 图标**：创建 .svg 格式和多尺寸 PNG
6. **安装程序图标**：如果使用 Inno Setup 等，配置安装程序图标
7. **文件关联图标**：如果应用支持打开特定文件格式

---

## 时间估算

- Task 1: 创建脚本基础结构 - 15 分钟
- Task 2: 生成图标文件 - 10 分钟
- Task 3: 集成到构建流程 - 10 分钟
- Task 4: 更新系统托盘 - 15 分钟
- Task 5: 测试验证 - 20 分钟
- Task 6: 文档更新 - 10 分钟
- Task 7: 最终清理 - 10 分钟

**总计约 90 分钟**（不包括设计决策和迭代调整时间）
