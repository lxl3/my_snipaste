# MySnipaste

一个受 Snipaste 启发的跨平台截图工具，基于 PySide6 构建。支持截图、贴图、标注和 OCR 文字识别。

## 功能特性

### 截图
- **F12 快捷键** - 按下 F12 启动全屏截图覆盖层
- **多显示器支持** - 自动适配多屏环境和高 DPI 显示
- **选区调整** - 拖动边框和角点精确调整选区，实时显示尺寸信息

### 标注工具
截图后可直接使用丰富的标注工具：
- **形状** - 矩形、圆形（支持预设颜色和自定义取色器）
- **箭头/线条** - 有箭头 / 无箭头两种模式
- **画笔** - 自由手绘，可调颜色和粗细
- **马赛克** - 对敏感区域打码
- **文字** - 支持字体选择、字号调整、加粗/斜体、多色选择

### 贴图（Pin）
- 将截图固定在桌面最顶层，双击关闭
- 可拖动调整位置

### OCR 文字识别
- **内置 Tesseract OCR 引擎** - 无需额外安装任何依赖
- **中英文识别** - 自动检测最优语言（eng + chi_sim）
- **截图 OCR** - 在截图中直接识别文字并复制到剪贴板
- **剪贴板 OCR** - 对剪贴板中的图片进行文字识别
- **异步处理** - 后台线程执行，可随时取消

### 其他
- **系统托盘** - 托盘菜单快速访问截图和 OCR 功能
- **撤销/重做** - 完整的标注操作历史
- **保存/复制** - 导出为 PNG/JPEG 或复制到剪贴板
- **Ctrl+滚轮缩放** - 在编辑器中缩放查看截图

## 快速开始

### 运行源码

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/my_snipaste.git
cd my_snipaste

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行
python main.py
```

> **注意**: 从源码运行时，OCR 功能需要系统已安装 [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) 并配置好语言包。

### 使用打包版本（推荐）

直接运行 `dist/MySnipaste.exe` 即可，**无需安装任何额外软件**。

打包版本已内置：
- Tesseract OCR 引擎 v5.5.0
- 英文语言包（eng）
- 简体中文语言包（chi_sim）

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `F12` | 启动截图 |
| `Esc` | 取消截图 |
| `Ctrl + 滚轮` | 编辑器中缩放截图 |
| `双击` | 关闭贴图窗口 |

## 构建打包

### 完整构建（包含 Tesseract）

```bash
python build.py
```

构建脚本会自动：
1. 准备 Tesseract 可执行文件和语言数据
2. 将所有依赖打包进单个 exe 文件

### 跳过下载（使用已有 bundle）

```bash
python build.py --skip-download
```

使用 `tesseract_bundle/` 目录中已有的文件进行打包。

### 输出

打包完成后，exe 文件位于：
```
dist/MySnipaste.exe
```

## 项目结构

```
my_snipaste/
├── main.py              # 入口文件
├── build.py             # 构建脚本（自动下载 Tesseract 并打包）
├── requirements.txt     # Python 依赖
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

## 技术栈

- **Python 3.12+**
- **PySide6** - Qt6 的 Python 绑定，用于 GUI
- **Pillow** - 图像处理
- **pytesseract** - Tesseract OCR 的 Python 接口
- **pynput** - 全局快捷键监听
- **mss** - 跨平台屏幕截图
- **PyInstaller** - 打包为独立 exe

## 许可证

MIT
