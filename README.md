# openSnipaste

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
git clone https://github.com/your-username/opensnipaste.git
cd opensnipaste

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行
python main.py
```

> **注意**: 从源码运行时，OCR 功能需要系统已安装 [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) 并配置好语言包。

### 使用打包版本（推荐）

直接运行 `dist/openSnipaste.exe` 即可，**无需安装任何额外软件**。

打包版本已内置：
- Tesseract OCR 引擎 v5.5.0
- 英文语言包（eng）
- 简体中文语言包（chi_sim）

## macOS 特别说明

### 快捷键
macOS 上使用 **`Cmd + Shift + X`**（而非 F12），因为 F12 被系统保留用于音量/亮度控制。

### 权限要求（打包版本）

打包的 `.app` 版本需要以下权限才能正常工作：

**必需权限：**
- **Input Monitoring（输入监控）** - 用于全局快捷键
- **Screen Recording（屏幕录制）** - 用于截图功能

**授予权限的步骤：**

1. 打开 **系统设置** → **隐私与安全性** → **输入监控**
2. 点击锁图标解锁（需要管理员密码）
3. 点击 **+** 按钮，选择 **openSnipaste.app**
4. 勾选启用
5. **完全退出并重启应用**（从托盘菜单选择「退出」）

**检查权限状态：**
- 从托盘菜单选择「检查权限」
- 或查看启动时的提示对话框

> **为什么开发模式（`python main.py`）可以，打包后不行？**
> 
> - 开发模式：权限主体是 Terminal.app（可能已有权限）
> - 打包版本：权限主体是 openSnipaste.app（需要单独授权）

详细说明见 [快捷键配置文档](docs/HOTKEYS.md)。

## 快捷键

### Windows / Linux

| 快捷键 | 功能 |
|--------|------|
| `F12` | 启动截图 |
| `Esc` | 取消截图 / 退出文字编辑 |
| `Ctrl + Z` | 撤销标注 |
| `Ctrl + Y` | 重做标注 |
| `Ctrl + C` | 复制截图到剪贴板 |
| `Ctrl + S` | 保存截图 |
| `Ctrl + P` | 贴图（钉到桌面） |
| `双击` | 关闭贴图窗口 |

### macOS

| 快捷键 | 功能 |
|--------|------|
| `Cmd + Shift + X` | 启动截图 |
| `Esc` | 取消截图 / 退出文字编辑 |
| `Cmd + Z` | 撤销标注 |
| `Cmd + Shift + Z` | 重做标注 |
| `Cmd + C` | 复制截图到剪贴板 |
| `Cmd + S` | 保存截图 |
| `Cmd + P` | 贴图（钉到桌面） |
| `双击` | 关闭贴图窗口 |

## 构建打包

### 完整构建（包含 Tesseract）

```bash
python scripts/build_windows.py
```

构建脚本会自动：
1. 准备 Tesseract 可执行文件和语言数据
2. 将所有依赖打包进单个 exe 文件

### 跳过下载（使用已有 bundle）

```bash
python scripts/build_windows.py --skip-download
```

使用 `tesseract_bundle/` 目录中已有的文件进行打包。

### 输出

打包完成后，exe 文件位于：
```
dist/openSnipaste.exe
```

## 项目结构

```
opensnipaste/
├── main.py                    # 入口文件
├── pyproject.toml             # 项目配置（版本、pytest、ruff）
├── requirements.txt           # Python 依赖
├── requirements-dev.txt       # 开发依赖（pytest, ruff）
├── icon.icns                  # macOS 应用图标
├── icon.ico                   # Windows 应用图标
├── assets/
│   └── icons/                 # 多尺寸 PNG 图标
├── src/
│   ├── __init__.py            # 包初始化，版本定义
│   ├── app.py                 # 主应用：托盘、快捷键、截图流程
│   ├── core/                  # 基础层
│   │   ├── settings.py        # JSON 持久化设置
│   │   ├── hotkeys.py         # 全局快捷键监听
│   │   ├── permissions.py     # macOS 权限管理
│   │   ├── utils.py           # 图标加载、截图、PIL-Qt 转换
│   │   ├── constants.py       # 设计常量
│   │   └── logger.py          # 彩色日志 + 文件轮转
│   ├── overlay/               # 截图覆盖层
│   │   ├── widget.py          # 全屏覆盖层 + 选区
│   │   ├── toolbar.py         # 标注工具栏
│   │   ├── actions.py         # OCR / 钉/复制/保存 / 撤销重做
│   │   ├── rendering.py       # 标注渲染
│   │   └── ocr_mixin.py       # OCR 进度弹窗
│   ├── ocr/
│   │   └── engine.py          # Tesseract OCR 引擎
│   └── ui/
│       ├── tray.py            # 系统托盘
│       ├── pin_window.py      # 贴图窗口
│       ├── settings_dialog.py # 设置对话框
│       └── ocr_dialog.py      # OCR 结果查看
├── scripts/
│   ├── build_common.py        # 共享构建逻辑
│   ├── build_macos.py         # macOS PyInstaller 构建
│   ├── build_windows.py       # Windows 构建（自动下载 Tesseract）
│   ├── build_nuitka_macos.py  # macOS Nuitka 构建（实验）
│   └── generate_icon.py       # 图标生成
├── tests/
│   ├── test_settings.py       # 设置测试
│   ├── test_hotkeys.py        # 热键测试
│   ├── test_constants.py      # 常量测试
│   ├── test_utils.py          # 工具函数测试
│   ├── test_permissions.py    # 权限测试
│   ├── test_ocr_engine.py     # OCR 引擎测试
│   └── test_icon_generation.py# 图标生成测试
├── tesseract_bundle/          # Windows Tesseract 打包文件
├── docs/                      # 文档
└── .github/workflows/         # GitHub Actions CI
```

## 技术栈

- **Python 3.12+**
- **PySide6** - Qt6 的 Python 绑定，用于 GUI
- **Pillow** - 图像处理
- **pytesseract** - Tesseract OCR 的 Python 接口
- **pynput** - 全局快捷键监听
- **PyInstaller** - 打包为独立 exe

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

## 许可证

MIT
