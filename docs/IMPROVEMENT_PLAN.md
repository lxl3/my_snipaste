# MySnipaste 项目改进建议

## 概述
这是对 MySnipaste 截图工具项目的全面评估和改进建议。项目整体架构良好,文档完善,但在测试覆盖率、代码质量、项目配置等方面还有提升空间。

---

## 一、测试相关改进 🧪

### 1.1 修复失败的测试 (高优先级)
**当前问题**: 4个测试失败,63个通过
- `tests/test_settings.py::test_default_hotkey` - 默认快捷键断言失败
- `tests/test_settings.py::test_load_missing_file_returns_defaults` - 加载不存在文件测试失败  
- `tests/test_settings.py::test_load_corrupted_json_returns_defaults` - 加载损坏JSON测试失败
- `tests/test_hotkeys.py::test_normalize_other_key_unchanged` - 按键规范化测试失败

**根本原因**:
- `test_default_hotkey` 假设所有平台默认都是 "cmd+shift+x",但实际 Windows 是 "f12"
- 配置测试中 `temp_settings_dir` fixture 可能没有正确设置环境

**修复方法**:
```python
# tests/test_settings.py - 修复平台相关测试
def test_default_hotkey(self, monkeypatch):
    # 根据平台验证不同的默认值
    import sys
    if sys.platform == 'darwin':
        assert AppSettings().hotkey == "cmd+shift+x"
    else:
        assert AppSettings().hotkey == "f12"
```

### 1.2 大幅提升测试覆盖率 (高优先级)
**当前覆盖率**: 20% (非常低)

**未覆盖的关键模块**:
- `src/overlay/widget.py` - 10% (核心截图功能)
- `src/overlay/toolbar.py` - 12% (工具栏交互)
- `src/ui/settings_dialog.py` - 9% (设置界面)
- `src/ui/ocr_dialog.py` - 0% (OCR 结果展示)
- `src/app.py` - 15% (主应用逻辑)

**改进目标**: 将覆盖率提升到 60-70%

**测试策略**:
1. **单元测试**: 为核心业务逻辑添加测试
   - 标注功能 (annotations in widget.py)
   - 选区调整逻辑
   - 撤销/重做机制
   
2. **集成测试**: 测试组件交互
   - 截图 → 标注 → 保存流程
   - OCR 工作流
   - 快捷键触发流程

3. **Mock 测试**: 隔离外部依赖
   - Mock QApplication.clipboard
   - Mock Tesseract OCR
   - Mock 文件系统操作

**示例测试**:
```python
# tests/test_overlay_widget.py
def test_selection_rect_adjustment():
    overlay = CaptureOverlay(mock_screenshot)
    overlay.selection_rect = QRect(100, 100, 200, 200)
    
    # 测试调整右下角
    overlay._drag_mode = "bottom_right"
    overlay._adjust_selection(QPoint(350, 350))
    
    assert overlay.selection_rect.width() == 250
    assert overlay.selection_rect.height() == 250

def test_add_annotation_clears_redo_stack():
    overlay = CaptureOverlay(mock_screenshot)
    overlay.annotations = [{"type": "rect", ...}]
    overlay._redo_stack = [{"type": "ellipse", ...}]
    
    overlay._add_annotation({"type": "arrow", ...})
    
    assert len(overlay._redo_stack) == 0
```

### 1.3 CI 中添加测试步骤 (中优先级)
**当前问题**: `.github/workflows/build-cross-platform.yml` 只有构建,没有测试

**改进**:
```yaml
jobs:
  test:
    name: Run Tests
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.12']
    
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests with coverage
      run: |
        pytest --cov=src --cov-report=xml --cov-report=term
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  build-windows:
    needs: test  # 只在测试通过后构建
    # ...
```

---

## 二、代码质量改进 🔧

### 2.1 安装并配置代码检查工具 (高优先级)
**当前问题**: 
- `ruff check` 命令不可用 (ruff 未安装)
- 缺少自动化代码质量检查

**改进**:
```bash
# 安装 ruff
pip install -r requirements-dev.txt

# 添加更多 lint 规则
# pyproject.toml
[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "W",   # pycodestyle warnings
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "SIM", # flake8-simplify
    "RET", # flake8-return
]
```

### 2.2 拆分大文件 (中优先级)
**当前问题**:
- `src/ui/settings_dialog.py` - 757 行 (过大)
- `src/overlay/widget.py` - 696 行 (过大)
- `src/overlay/toolbar.py` - 541 行 (较大)

**建议重构**:

**settings_dialog.py** 拆分为:
```
src/ui/settings/
├── __init__.py
├── dialog.py           # 主对话框框架 (~150行)
├── general_tab.py      # 通用设置页 (~150行)
├── hotkey_tab.py       # 快捷键设置页 (~150行)
├── capture_tab.py      # 截图选项页 (~150行)
├── advanced_tab.py     # 高级设置页 (~150行)
└── widgets.py          # 共享组件 (HotkeyRecorderWidget等)
```

**widget.py** 拆分为:
```
src/overlay/
├── widget.py           # 主覆盖层框架 (~200行)
├── selection.py        # 选区管理逻辑 (~150行)
├── mouse_handler.py    # 鼠标事件处理 (~150行)
├── keyboard_handler.py # 键盘事件处理 (~100行)
└── paint_handler.py    # 绘制逻辑 (~100行)
```

### 2.3 添加类型注解 (中优先级)
**当前状况**: 部分函数有类型注解,但不完整

**改进**:
```python
# 添加 mypy 配置
# pyproject.toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true  # 要求所有函数都有类型注解

# 示例改进
# src/overlay/rendering.py
def _render_rect(
    painter: QPainter,
    ann: dict[str, Any],  # 后续可改为 TypedDict
) -> None:
    """渲染矩形标注"""
    ...
```

### 2.4 添加 pre-commit 钩子 (低优先级)
**目的**: 在提交前自动检查代码质量

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

---

## 三、文档完善 📚

### 3.1 添加项目标准文档 (中优先级)

**缺失的文档**:

**CONTRIBUTING.md** - 贡献指南
```markdown
# 贡献指南

## 开发环境设置
1. Fork 仓库
2. 克隆: `git clone ...`
3. 安装依赖: `pip install -r requirements.txt -r requirements-dev.txt`
4. 运行测试: `pytest`

## 代码规范
- 使用 ruff 进行代码格式化: `ruff format .`
- 运行 lint 检查: `ruff check .`
- 确保测试覆盖率不降低

## 提交规范
- feat: 新功能
- fix: 修复
- docs: 文档
- test: 测试
- refactor: 重构

## Pull Request 流程
1. 创建功能分支
2. 编写测试
3. 确保所有测试通过
4. 提交 PR
```

**CHANGELOG.md** - 版本变更记录
```markdown
# Changelog

## [Unreleased]
### Added
- 倒计时覆盖层功能

### Fixed
- macOS 托盘右键点击无响应

## [1.0.1] - 2026-05-27
### Added
- 截图延迟功能
- 截图声音选项

### Fixed
- 快捷键组合键不生效
...
```

**LICENSE** - 开源许可证
```
MIT License

Copyright (c) 2026 MySnipaste Team
...
```

### 3.2 完善国际化支持 (中优先级)
**当前状态**: 只有中文翻译 (zh_CN.json, zh_TW.json)

**改进**:
1. 添加英文翻译 `src/resources/locales/en_US.json`
2. 确保所有UI字符串都使用 `_()` 函数包裹
3. 添加语言切换测试

```bash
# 检查未翻译的字符串
grep -r "QLabel\|QPushButton\|QMessageBox" src/ui/ | grep -v "_(" | grep '"'
```

### 3.3 添加 API 文档 (低优先级)
**使用 Sphinx 生成代码文档**:
```python
# docs/conf.py
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',  # 支持 Google/NumPy 风格的 docstring
    'sphinx.ext.viewcode',
]
```

---

## 四、架构优化 🏗️

### 4.1 引入依赖注入 (低优先级)
**当前问题**: 全局单例模式 (`get_settings()`) 使测试困难

**改进**:
```python
# 重构为依赖注入
class SnipasteApp(QApplication):
    def __init__(self, settings: AppSettings | None = None):
        super().__init__()
        self.settings = settings or AppSettings.load()
        
# 测试时可注入 mock
def test_app_with_custom_settings():
    test_settings = AppSettings(hotkey="f1")
    app = SnipasteApp(settings=test_settings)
    assert app.settings.hotkey == "f1"
```

### 4.2 引入事件总线 (低优先级)
**目的**: 解耦组件间的直接依赖

```python
# src/core/events.py
from PySide6.QtCore import QObject, Signal

class EventBus(QObject):
    """全局事件总线"""
    screenshot_captured = Signal(object)  # QPixmap
    annotation_added = Signal(dict)
    ocr_completed = Signal(str)
    
_event_bus = EventBus()

def get_event_bus() -> EventBus:
    return _event_bus
```

### 4.3 标注数据结构类型化 (中优先级)
**当前问题**: 标注使用 `dict`,缺少类型安全

**改进**:
```python
# src/overlay/annotations.py
from dataclasses import dataclass
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

@dataclass
class BaseAnnotation:
    type: str
    color: QColor
    width: int

@dataclass
class RectAnnotation(BaseAnnotation):
    type: str = "rect"
    start: QPointF
    end: QPointF
    filled: bool = False

@dataclass  
class TextAnnotation(BaseAnnotation):
    type: str = "text"
    position: QPointF
    text: str
    font_family: str
    font_size: int
    bold: bool = False
    italic: bool = False
```

---

## 五、功能增强 ✨

### 5.1 性能优化 (中优先级)

**问题**: 大量标注时可能卡顿

**优化方案**:
1. **标注渲染缓存**
```python
# src/overlay/widget.py
class CaptureOverlay(QWidget):
    def __init__(self):
        self._annotation_cache: QPixmap | None = None
        self._cache_dirty = True
    
    def _add_annotation(self, ann):
        self.annotations.append(ann)
        self._cache_dirty = True  # 标记缓存失效
    
    def paintEvent(self, event):
        # 只有标注改变时才重新渲染
        if self._cache_dirty:
            self._annotation_cache = self._render_to_pixmap()
            self._cache_dirty = False
        painter.drawPixmap(0, 0, self._annotation_cache)
```

2. **延迟加载图标**
```python
# src/resources/icons/toolbar_icons.py
from functools import lru_cache

@lru_cache(maxsize=32)
def get_icon(name: str, color: str) -> QIcon:
    # 缓存已生成的图标
    ...
```

### 5.2 错误处理增强 (中优先级)

**添加全局异常处理**:
```python
# src/app.py
def excepthook(exc_type, exc_value, exc_traceback):
    """全局异常处理"""
    logger.error(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    # 显示友好的错误对话框
    QMessageBox.critical(
        None,
        _("Error"),
        _("An unexpected error occurred. Please check the logs.")
    )

sys.excepthook = excepthook
```

### 5.3 添加崩溃报告 (低优先级)
**使用 Sentry 或本地日志上传**:
```python
# requirements.txt
sentry-sdk>=1.40.0

# src/app.py
import sentry_sdk
sentry_sdk.init(
    dsn="https://...",
    environment="production",
    release=f"mysnipaste@{__version__}"
)
```

---

## 六、开发体验改进 🛠️

### 6.1 添加 .editorconfig (低优先级)
```ini
# .editorconfig
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
indent_style = space
indent_size = 4
max_line_length = 120

[*.{yml,yaml,json}]
indent_style = space
indent_size = 2
```

### 6.2 改进日志系统 (低优先级)
**添加结构化日志**:
```python
# src/core/logger.py
import structlog

logger = structlog.get_logger()
logger.info(
    "screenshot_captured",
    width=1920,
    height=1080,
    annotation_count=5
)
```

### 6.3 开发脚本 (低优先级)
```bash
# scripts/dev.sh
#!/bin/bash
# 一键启动开发环境

# 检查依赖
python -m pip install -r requirements.txt -r requirements-dev.txt

# 运行测试
pytest --cov=src

# 启动应用
python main.py
```

---

## 实施优先级总结

### 🔴 高优先级 (建议立即处理)
1. ✅ 修复 4 个失败的测试
2. ✅ 安装并配置 ruff 代码检查
3. ✅ 提升测试覆盖率至 60%+ (至少覆盖核心模块)

### 🟡 中优先级 (建议 1-2 周内处理)
1. ✅ 添加 CI 测试步骤
2. ✅ 拆分大文件 (settings_dialog.py, widget.py)
3. ✅ 完善英文国际化
4. ✅ 添加 CONTRIBUTING.md, CHANGELOG.md, LICENSE
5. ✅ 标注数据结构类型化
6. ✅ 添加类型注解 + mypy

### 🟢 低优先级 (可长期规划)
1. ⚪ 添加 pre-commit 钩子
2. ⚪ 引入依赖注入模式
3. ⚪ 添加 API 文档 (Sphinx)
4. ⚪ 性能优化 (标注缓存)
5. ⚪ 添加崩溃报告
6. ⚪ 开发脚本和工具

---

## 验证计划

完成改进后,通过以下步骤验证:

```bash
# 1. 所有测试通过
pytest -v
# 预期: 67+ passed, 0 failed

# 2. 测试覆盖率达标
pytest --cov=src --cov-report=term
# 预期: Total coverage >= 60%

# 3. 代码质量检查通过
ruff check src/
ruff format --check src/
# 预期: 0 errors, 0 warnings

# 4. 类型检查通过
mypy src/
# 预期: Success: no issues found

# 5. 构建成功
python scripts/build_windows.py
# 预期: dist/MySnipaste.exe 生成成功

# 6. 功能测试
python main.py
# 手动测试: 截图、标注、OCR、贴图、保存
```

---

## 预期收益

- **代码质量**: 更稳定、更易维护
- **开发效率**: 自动化检查减少人工审查
- **新贡献者**: 完善的文档降低贡献门槛  
- **用户体验**: 更少的 bug,更好的性能
- **项目可持续性**: 标准化流程保证长期健康发展
