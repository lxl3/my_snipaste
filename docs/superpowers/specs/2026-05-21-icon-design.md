# openSnipaste 图标设计规格

**日期**: 2026-05-21  
**设计者**: Claude (with user collaboration)  
**状态**: 已批准

## 设计概述

为 openSnipaste 截图工具设计应用图标，需要同时体现截图和 OCR 文字识别两个核心功能。图标将用于 Windows 系统的各种场景：桌面快捷方式、任务栏、系统托盘等。

### 设计目标

1. **功能表达**: 清晰传达截图和 OCR 文字识别功能
2. **品牌识别**: 在众多应用中脱颖而出，易于记忆
3. **跨尺寸**: 在 16x16 到 256x256 所有尺寸下保持清晰
4. **专业感**: 符合工具类应用的专业定位

## 设计方案

### 核心理念

**圆角矩形框 + 字母 'A'**

- **圆角矩形框**: 象征截图选区边框，代表截图功能
- **字母 'A'**: 代表文字（Alphabet）和 OCR 文字识别功能
- **组合含义**: "从截图中识别文字"

### 视觉风格

**扁平化设计 (Flat Design)**

- 纯色填充，无渐变
- 无阴影、无立体效果
- 简洁几何形状
- 高对比度
- 符合现代设计趋势（Windows 11、VS Code、Notion 等）

**优势**:
- 清晰简洁
- 各尺寸都清晰可辨
- 现代感强
- 易于维护和修改

### 配色方案

**深灰色系 (Professional Gray)**

```
主色（框线）: #2C3E50  深灰色
辅助色:      #34495E  中灰色 (用于变体/阴影)
文字色:      #ECF0F1  浅灰白色
背景:        透明 或 #2C3E50
```

**选择理由**:
- 低调专业，符合工具类应用定位
- 适合深色模式
- 与 GitHub Desktop 等专业工具一致的调性

**权衡**:
- 浅色背景下可能不如亮色醒目，但专业感更强
- 需要确保在白色背景下有足够对比度（可通过加深颜色或添加细边框解决）

## 详细规格

### 尺寸规格 (基于 256x256)

```
画布尺寸:        256x256 px
外框尺寸:        200x200 px
边距:           28px (每边)
圆角半径:        24px (约 12% 的框宽)
框线宽度:        8px
字母 'A' 高度:   120px
字母 'A' 笔画:   20px (Medium/Bold 字重)
字母位置:        水平垂直居中
```

### 多尺寸适配

图标需要在不同尺寸下保持清晰可辨，采用分级简化策略：

#### 256x256 (大图标/快捷方式)
- 完整细节显示
- 框线 8px
- 字母 'A' 高度 120px
- 圆角 24px

#### 128x128 (中等尺寸)
- 框线 6px
- 字母 'A' 高度 70px
- 圆角 16px
- 保持完整细节

#### 48x48 (任务栏)
- 框线 4px
- 字母 'A' 高度 28px
- 圆角 6px
- 简化细节，保持识别度

#### 32x32 (小图标)
- 框线 3px
- 字母 'A' 高度 20px
- 圆角 4px
- 字母加粗显示以提高清晰度

#### 16x16 (系统托盘)
- 框线 2px
- 字母 'A' 高度 10px
- 圆角 2px
- 最简化设计，确保可辨识

### 视觉层次

1. **主要元素**: 圆角矩形框（截图功能）
2. **次要元素**: 字母 'A'（OCR 功能）
3. **背景**: 透明或深灰色填充

## 技术实现

### 文件格式

#### ICO 格式 (主要格式)

**文件**: `icon.ico`

**包含尺寸**:
- 16x16
- 32x32
- 48x48
- 128x128
- 256x256

**用途**:
- PyInstaller 打包
- Windows 快捷方式图标
- 任务栏图标
- 文件关联图标

#### PNG 格式 (备用格式)

**文件命名**:
- `icon-16.png`
- `icon-32.png`
- `icon-48.png`
- `icon-128.png`
- `icon-256.png`

**规格**:
- 透明背景
- 32-bit RGBA

**用途**:
- 系统托盘显示（PySide6 需要）
- 应用内图标显示
- 跨平台兼容

### 创建方式

#### 方案 A: Python 脚本生成 (推荐)

**优势**:
- 完全可编程，易于调整参数
- 自动生成所有尺寸
- 矢量绘制，质量高
- 版本控制友好

**实现步骤**:
1. 使用 Pillow 库绘制图标
2. 创建 `scripts/generate_icon.py` 脚本
3. 生成所有尺寸的 PNG
4. 使用 Pillow 或 `pillow-ico` 合并为 ICO

**关键代码结构**:
```python
from PIL import Image, ImageDraw, ImageFont

def draw_icon(size):
    # 创建透明画布
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 计算尺寸参数
    padding = size * 0.11
    box_size = size - 2 * padding
    border_width = max(2, size // 32)
    corner_radius = max(2, size // 11)
    
    # 绘制圆角矩形框
    draw.rounded_rectangle(
        [padding, padding, size-padding, size-padding],
        radius=corner_radius,
        outline='#2C3E50',
        width=border_width
    )
    
    # 绘制字母 'A'
    font_size = int(size * 0.47)
    # ... 绘制文字逻辑
    
    return img
```

#### 方案 B: 设计工具 (备选)

**工具选项**:
- Figma (在线，免费)
- Inkscape (开源)
- Adobe Illustrator (商业)

**流程**:
1. 在设计工具中创建 256x256 矢量图
2. 导出为各个尺寸的 PNG
3. 使用在线工具（如 icoconverter.com）转换为 ICO

### PyInstaller 集成

#### 方法 1: 修改 spec 文件

在 `openSnipaste.spec` 中添加图标：

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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='icon.ico',  # 添加此行
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

#### 方法 2: 修改 build.py

在 `build.py` 的 PyInstaller 命令中添加：

```python
cmd = [
    sys.executable, '-m', 'PyInstaller',
    '--onefile',
    '--windowed',
    '--name', BUILD_NAME,
    '--icon', 'icon.ico',  # 添加此行
    '--noconfirm',
    ...
]
```

### 项目结构

```
opensnipaste/
├── icon.ico                 # 主图标文件（多尺寸）
├── assets/
│   └── icons/
│       ├── icon-16.png      # 各尺寸 PNG
│       ├── icon-32.png
│       ├── icon-48.png
│       ├── icon-128.png
│       └── icon-256.png
├── scripts/
│   └── generate_icon.py     # 图标生成脚本
├── build.py                 # 更新添加图标参数
└── openSnipaste.spec          # 更新添加图标路径
```

## 实现计划

### 阶段 1: 创建图标生成脚本
- [ ] 创建 `scripts/generate_icon.py`
- [ ] 实现绘制逻辑（圆角矩形 + 字母 A）
- [ ] 实现多尺寸生成
- [ ] 生成 PNG 和 ICO 文件

### 阶段 2: 集成到构建流程
- [ ] 更新 `openSnipaste.spec` 添加图标路径
- [ ] 更新 `build.py` 添加图标参数
- [ ] 测试打包后的图标显示

### 阶段 3: 系统托盘图标
- [ ] 在 `src/app.py` 中加载图标
- [ ] 确保系统托盘显示正确

### 阶段 4: 验证测试
- [ ] 测试所有尺寸的显示效果
- [ ] 测试浅色/深色背景下的对比度
- [ ] 测试 Windows 各个场景（快捷方式、任务栏、托盘）

## 设计权衡

### 已选择的权衡

1. **深灰色 vs 亮色**
   - 选择深灰色以体现专业感
   - 权衡：浅色背景下可能不够醒目
   - 缓解：确保足够的对比度，必要时添加细边框

2. **字母 'A' vs 'OCR' 文字**
   - 选择单字母 'A' 以提高小尺寸清晰度
   - 权衡：可能不如 'OCR' 文字直接
   - 理由：16x16 尺寸下单字母更清晰

3. **截图框 vs 剪刀**
   - 选择截图框而非 Snipaste 经典的剪刀
   - 权衡：降低了品牌连续性
   - 理由：用户明确要求能体现 OCR 功能，框+文字的组合更直观

### 未来可能的调整

1. **颜色调整**: 如果发现浅色背景下对比度不足，可以：
   - 加深主色到 #1a252f
   - 添加 1px 浅色外边框

2. **元素简化**: 如果 16x16 尺寸下 'A' 字母仍不够清晰，可以：
   - 改为实心圆点
   - 改为三条横线（抽象表示文字）

## 附录

### 参考图标

**类似风格**:
- VS Code: 扁平化蓝色图标
- Notion: 扁平化黑白图标
- GitHub Desktop: 深灰色调专业图标

### 字体选择

如果使用字体渲染 'A' 字母，推荐字体：
- **Sans-serif**: Arial, Helvetica, Roboto
- **粗细**: Bold 或 Black
- **特点**: 笔画均匀，易于识别

### 工具和库

- **Pillow**: Python 图像处理库
- **pillow-ico**: 创建 ICO 文件（可选，Pillow 本身支持）
- **PyInstaller**: Python 打包工具

### 色彩无障碍

深灰色 #2C3E50 与白色 #FFFFFF 的对比度约为 **12.6:1**，满足 WCAG AAA 级别（需要 7:1），确保色盲用户也能清晰识别。

---

**设计批准**: ✓ 用户已确认  
**下一步**: 创建实现计划并执行
