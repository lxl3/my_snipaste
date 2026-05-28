# UX 快速优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Toast 提示、快捷键帮助、颜色记忆、历史列表和工具设置记忆，提升用户体验

**Architecture:** 
- Toast 系统：单例管理器 + 独立组件，支持堆叠和动画
- 快捷键帮助：半透明浮层组件，按需显示
- 颜色/设置记忆：扩展 AppSettings，持久化到 JSON
- 历史管理：独立模块 + 托盘菜单集成

**Tech Stack:** PySide6, Python 3.12, QPropertyAnimation, JSON 持久化

---

## 文件规划

**新建文件**:
- `src/ui/toast.py` - Toast 提示组件和管理器
- `src/overlay/hotkey_panel.py` - 快捷键帮助面板
- `src/core/screenshot_history.py` - 截图历史管理
- `tests/test_toast.py` - Toast 单元测试
- `tests/test_screenshot_history.py` - 历史管理单元测试

**修改文件**:
- `src/core/settings.py` - 添加新配置字段
- `src/overlay/widget.py` - 集成快捷键面板、应用设置记忆
- `src/overlay/actions.py` - 添加 Toast 调用、保存历史
- `src/overlay/toolbar.py` - 颜色记忆 UI
- `src/overlay/ocr_mixin.py` - OCR Toast 提示
- `src/ui/tray.py` - 历史菜单
- `src/resources/locales/zh_CN.json` - 新增翻译
- `src/resources/locales/en_US.json` - 新增翻译（如果存在）

---

## Task 1: Toast 提示系统 - 核心组件

**Files:**
- Create: `src/ui/toast.py`
- Create: `tests/test_toast.py`

- [ ] **Step 1.1: 编写 Toast 组件测试**

```python
# tests/test_toast.py
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from src.ui.toast import ToastNotification, ToastManager

@pytest.fixture(scope="module")
def qapp():
    """Qt应用fixture"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

def test_toast_creation(qapp):
    """测试 Toast 创建"""
    toast = ToastNotification("测试消息", "✓", "success")
    assert toast.message == "测试消息"
    assert toast.icon == "✓"
    assert toast.toast_type == "success"

def test_toast_manager_singleton(qapp):
    """测试 ToastManager 单例"""
    manager1 = ToastManager.instance()
    manager2 = ToastManager.instance()
    assert manager1 is manager2

def test_toast_show(qapp):
    """测试 Toast 显示"""
    ToastManager.show("测试", "✓", "success", duration=100)
    # Toast 应该被添加到管理器
    assert len(ToastManager.instance()._toasts) > 0
```

- [ ] **Step 1.2: 运行测试确认失败**

```bash
pytest tests/test_toast.py -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'src.ui.toast'`

- [ ] **Step 1.3: 实现 Toast 核心组件**

```python
# src/ui/toast.py
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve
from PySide6.QtGui import QColor, QPainter

from ..core.i18n import _


class ToastNotification(QWidget):
    """Toast 提示组件"""
    
    # 颜色方案
    COLORS = {
        "success": QColor(40, 167, 69, 242),  # rgba(40, 167, 69, 0.95)
        "info": QColor(0, 123, 255, 242),      # rgba(0, 123, 255, 0.95)
        "error": QColor(220, 53, 69, 242),     # rgba(220, 53, 69, 0.95)
    }
    
    def __init__(self, message: str, icon: str = "✓", 
                 toast_type: str = "success", parent=None):
        super().__init__(parent)
        self.message = message
        self.icon = icon
        self.toast_type = toast_type
        self._hovered = False
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        # 布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(10)
        
        # 图标
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 18px; color: white;")
        layout.addWidget(icon_label)
        
        # 消息
        msg_label = QLabel(message)
        msg_label.setStyleSheet("font-size: 14px; font-weight: 500; color: white;")
        layout.addWidget(msg_label)
        
        self.adjustSize()
    
    def paintEvent(self, event):
        """绘制半透明背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 背景色
        color = self.COLORS.get(self.toast_type, self.COLORS["info"])
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        
        # 绘制圆角矩形
        painter.drawRoundedRect(self.rect(), 8, 8)
    
    def enterEvent(self, event):
        """鼠标进入"""
        self._hovered = True
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开"""
        self._hovered = False
        super().leaveEvent(event)
    
    def is_hovered(self) -> bool:
        """是否被鼠标悬停"""
        return self._hovered


class ToastManager:
    """Toast 管理器 - 单例模式"""
    
    _instance = None
    
    def __init__(self):
        self._toasts: list[ToastNotification] = []
        self._parent = None
        self._timers: dict[ToastNotification, QTimer] = {}
        self._animations: dict[ToastNotification, QPropertyAnimation] = {}
    
    @classmethod
    def instance(cls):
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def show(cls, message: str, icon: str = "✓", 
             toast_type: str = "success", duration: int = 2000,
             parent=None):
        """显示 Toast 提示"""
        manager = cls.instance()
        if parent:
            manager._parent = parent
        
        # 创建 Toast
        toast = ToastNotification(message, icon, toast_type, manager._parent)
        manager._toasts.append(toast)
        
        # 限制最多 3 个
        if len(manager._toasts) > 3:
            oldest = manager._toasts.pop(0)
            manager._hide_toast(oldest, animated=False)
        
        # 显示 Toast
        manager._show_toast(toast, duration)
    
    def _show_toast(self, toast: ToastNotification, duration: int):
        """显示 Toast 并设置自动隐藏"""
        # 定位到父窗口顶部居中
        if self._parent:
            parent_rect = self._parent.geometry()
            x = parent_rect.x() + (parent_rect.width() - toast.width()) // 2
            y = parent_rect.y() + 20
        else:
            # 无父窗口时使用屏幕中心
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - toast.width()) // 2
            y = 20
        
        # 进场动画：从上方滑入 + 淡入
        start_pos = QPoint(x, y - 50)
        end_pos = QPoint(x, y)
        
        toast.move(start_pos)
        toast.setWindowOpacity(0.0)
        toast.show()
        
        # 位置动画
        anim = QPropertyAnimation(toast, b"pos")
        anim.setDuration(300)
        anim.setStartValue(start_pos)
        anim.setEndValue(end_pos)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._animations[toast] = anim
        
        # 透明度动画（通过定时器模拟）
        opacity_steps = 10
        opacity_timer = QTimer()
        step = [0]
        
        def update_opacity():
            step[0] += 1
            toast.setWindowOpacity(step[0] / opacity_steps)
            if step[0] >= opacity_steps:
                opacity_timer.stop()
        
        opacity_timer.timeout.connect(update_opacity)
        opacity_timer.start(30)
        
        # 自动隐藏定时器
        timer = QTimer()
        elapsed = [0]
        
        def check_hide():
            if toast.is_hovered():
                return
            elapsed[0] += 100
            if elapsed[0] >= duration:
                timer.stop()
                self._hide_toast(toast)
        
        timer.timeout.connect(check_hide)
        timer.start(100)
        self._timers[toast] = timer
    
    def _hide_toast(self, toast: ToastNotification, animated: bool = True):
        """隐藏 Toast"""
        if toast in self._timers:
            self._timers[toast].stop()
            del self._timers[toast]
        
        if animated:
            # 淡出动画
            opacity_steps = 10
            opacity_timer = QTimer()
            step = [opacity_steps]
            
            def update_opacity():
                step[0] -= 1
                toast.setWindowOpacity(step[0] / opacity_steps)
                if step[0] <= 0:
                    opacity_timer.stop()
                    toast.close()
                    toast.deleteLater()
                    if toast in self._toasts:
                        self._toasts.remove(toast)
            
            opacity_timer.timeout.connect(update_opacity)
            opacity_timer.start(20)
        else:
            toast.close()
            toast.deleteLater()
            if toast in self._toasts:
                self._toasts.remove(toast)
```

- [ ] **Step 1.4: 运行测试确认通过**

```bash
pytest tests/test_toast.py -v
```

Expected: 3 passed

- [ ] **Step 1.5: 提交 Toast 核心组件**

```bash
git add src/ui/toast.py tests/test_toast.py
git commit -m "feat: 实现 Toast 提示核心组件

- 添加 ToastNotification 组件（半透明背景、图标、消息）
- 添加 ToastManager 单例管理器
- 支持进场/退场动画、鼠标悬停暂停
- 添加单元测试

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 2: Toast 集成到操作流程

**Files:**
- Modify: `src/overlay/actions.py`
- Modify: `src/overlay/widget.py`
- Modify: `src/overlay/ocr_mixin.py`

- [ ] **Step 2.1: 在保存/复制/贴图操作中添加 Toast**

```python
# src/overlay/actions.py
# 在文件顶部添加导入
from ..ui.toast import ToastManager

# 修改 _on_copy_action 方法（约在第 45 行附近）
# 找到这段代码：
#     QApplication.clipboard().setPixmap(result_pixmap)
#     self.close()
# 
# 在 self.close() 之前添加：
    ToastManager.show(_("Copied to clipboard"), "✓", "success", parent=self)

# 修改 _on_save_action 方法（约在第 60 行附近）
# 找到保存成功后的 self.close()
# 在它之前添加：
    ToastManager.show(_("Screenshot saved"), "✓", "success", parent=self)

# 修改 _on_pin_action 方法（约在第 75 行附近）
# 找到 self.pin_requested.emit(result_pixmap, pos)
# 在它之后添加：
    ToastManager.show(_("Pinned to desktop"), "📌", "success", parent=self)
```

- [ ] **Step 2.2: 在撤销/重做操作中添加 Toast**

```python
# src/overlay/widget.py
# 在文件顶部添加导入（如果还没有）
from ..ui.toast import ToastManager

# 找到 _undo 方法（约在第 450 行附近）
# 在方法末尾添加：
def _undo(self):
    if self.annotations:
        ann = self.annotations.pop()
        self._redo_stack.append(ann)
        self.update()
        ToastManager.show(_("Undone"), "↶", "info", parent=self)

# 找到 _redo 方法
# 在方法末尾添加：
def _redo(self):
    if self._redo_stack:
        ann = self._redo_stack.pop()
        self.annotations.append(ann)
        self.update()
        ToastManager.show(_("Redone"), "↷", "info", parent=self)
```

- [ ] **Step 2.3: 在 OCR 流程中添加 Toast**

```python
# src/overlay/ocr_mixin.py
# 在文件顶部添加导入
from ..ui.toast import ToastManager

# 找到 _do_ocr_screenshot 方法（约在第 30 行附近）
# 在显示进度对话框之前添加：
    ToastManager.show(_("OCR recognizing..."), "🔍", "info", parent=self)

# 找到 _on_ocr_finished 方法（OCR 成功回调）
# 在 QApplication.clipboard().setText(text) 之后添加：
    ToastManager.show(_("Recognition complete"), "✓", "success", parent=self)
```

- [ ] **Step 2.4: 添加翻译**

```json
// src/resources/locales/zh_CN.json
// 在现有翻译中添加以下键值对：
{
  "Copied to clipboard": "已复制到剪贴板",
  "Screenshot saved": "截图已保存",
  "Pinned to desktop": "已固定到桌面",
  "Undone": "已撤销",
  "Redone": "已重做",
  "OCR recognizing...": "OCR 识别中...",
  "Recognition complete": "识别完成"
}
```

- [ ] **Step 2.5: 手动测试 Toast 功能**

测试步骤：
1. 运行 `python main.py`
2. 按 F12 截图
3. 画一个矩形
4. 按 Ctrl+C - 应看到"已复制到剪贴板"提示
5. 按 Ctrl+Z - 应看到"已撤销"提示
6. 按 Ctrl+Y - 应看到"已重做"提示
7. 按 Ctrl+S 保存 - 应看到"截图已保存"提示

预期：Toast 显示在顶部居中，2秒后自动消失

- [ ] **Step 2.6: 提交 Toast 集成**

```bash
git add src/overlay/actions.py src/overlay/widget.py src/overlay/ocr_mixin.py src/resources/locales/zh_CN.json
git commit -m "feat: 集成 Toast 到操作流程

- 添加保存/复制/贴图成功提示
- 添加撤销/重做反馈
- 添加 OCR 进度和完成提示
- 添加中文翻译

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 3: 快捷键帮助面板

**Files:**
- Create: `src/overlay/hotkey_panel.py`
- Modify: `src/overlay/widget.py`

- [ ] **Step 3.1: 实现快捷键帮助面板组件**

```python
# src/overlay/hotkey_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor

from ..core.i18n import _


class HotkeyHelpPanel(QWidget):
    """快捷键帮助面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel(_("Hotkeys"))
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #333;")
        layout.addWidget(title)
        
        # 快捷键列表
        shortcuts = [
            (_("Copy"), "Ctrl+C"),
            (_("Save"), "Ctrl+S"),
            (_("Pin"), "Ctrl+P"),
            ("", ""),  # 分隔线
            (_("Undo"), "Ctrl+Z"),
            (_("Redo"), "Ctrl+Y"),
            ("", ""),  # 分隔线
            (_("Toggle help"), "? / F1"),
        ]
        
        for label, key in shortcuts:
            if not label:
                # 分隔线
                sep = QLabel()
                sep.setFixedHeight(1)
                sep.setStyleSheet("background: #e0e0e0;")
                layout.addWidget(sep)
            else:
                row = QWidget()
                row_layout = QVBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                
                row_label = QLabel(f'<span style="color: #555;">{label}</span>'
                                  f'<span style="float: right; background: #f0f0f0; '
                                  f'padding: 2px 8px; border-radius: 3px; font-size: 11px;">{key}</span>')
                row_label.setStyleSheet("font-size: 13px;")
                row_layout.addWidget(row_label)
                
                layout.addWidget(row)
        
        # 关闭提示
        close_hint = QLabel(_("Press Esc to close"))
        close_hint.setStyleSheet("font-size: 12px; color: #888;")
        close_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(close_hint)
        
        self.setFixedWidth(350)
        self.adjustSize()
    
    def paintEvent(self, event):
        """绘制半透明背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 背景：半透明白色 + 毛玻璃效果（简化版）
        color = QColor(255, 255, 255, 235)  # rgba(255, 255, 255, 0.92)
        painter.setBrush(color)
        painter.setPen(QColor(255, 255, 255, 77))  # 边框
        painter.drawRoundedRect(self.rect(), 6, 6)
```

- [ ] **Step 3.2: 在 CaptureOverlay 中集成快捷键面板**

```python
# src/overlay/widget.py
# 在文件顶部添加导入
from .hotkey_panel import HotkeyHelpPanel

# 在 __init__ 方法中添加（约在第 100 行附近，self.toolbar.setup() 之后）
        self._hotkey_panel = None

# 添加快捷键面板切换方法（在类的末尾）
    def _toggle_hotkey_panel(self):
        """切换快捷键帮助面板显示"""
        if self._hotkey_panel is None:
            self._hotkey_panel = HotkeyHelpPanel(self)
            # 居中显示
            panel_x = (self.width() - self._hotkey_panel.width()) // 2
            panel_y = (self.height() - self._hotkey_panel.height()) // 2
            self._hotkey_panel.move(panel_x, panel_y)
            self._hotkey_panel.show()
        elif self._hotkey_panel.isVisible():
            self._hotkey_panel.hide()
        else:
            self._hotkey_panel.show()

# 在 keyPressEvent 方法中添加（约在第 550 行附近）
# 在现有按键处理代码之前添加：
    def keyPressEvent(self, event):
        # 快捷键帮助
        if event.key() == Qt.Key_Question or event.key() == Qt.Key_F1:
            self._toggle_hotkey_panel()
            event.accept()
            return
        
        # ... 现有的按键处理代码
```

- [ ] **Step 3.3: 添加快捷键帮助翻译**

```json
// src/resources/locales/zh_CN.json
// 添加以下键值对：
{
  "Hotkeys": "快捷键",
  "Copy": "复制",
  "Save": "保存",
  "Pin": "贴图",
  "Undo": "撤销",
  "Redo": "重做",
  "Toggle help": "显示此帮助",
  "Press Esc to close": "按 Esc 关闭"
}
```

- [ ] **Step 3.4: 手动测试快捷键面板**

测试步骤：
1. 运行 `python main.py`
2. 按 F12 截图
3. 按 `?` 键 - 应显示快捷键帮助面板
4. 再按 `?` 或 `Esc` - 面板应关闭

预期：面板半透明，居中显示，列出所有快捷键

- [ ] **Step 3.5: 提交快捷键帮助面板**

```bash
git add src/overlay/hotkey_panel.py src/overlay/widget.py src/resources/locales/zh_CN.json
git commit -m "feat: 添加快捷键帮助面板

- 实现半透明浮层组件
- 按 ? 或 F1 切换显示
- 列出所有常用快捷键
- 添加中文翻译

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 4: 配置扩展 - 颜色记忆和工具设置

**Files:**
- Modify: `src/core/settings.py`
- Create: `tests/test_settings_memory.py`

- [ ] **Step 4.1: 编写配置扩展测试**

```python
# tests/test_settings_memory.py
from src.core.settings import AppSettings


def test_recent_colors_default():
    """测试最近颜色默认为空列表"""
    settings = AppSettings()
    assert settings.recent_colors == []


def test_add_recent_color():
    """测试添加最近颜色"""
    settings = AppSettings()
    settings.add_recent_color("#ff0000")
    assert "#ff0000" in settings.recent_colors


def test_recent_colors_max_limit():
    """测试最近颜色最多5个"""
    settings = AppSettings()
    for i in range(10):
        settings.add_recent_color(f"#00000{i}")
    assert len(settings.recent_colors) <= 5


def test_tool_settings_default():
    """测试工具设置默认为空字典"""
    settings = AppSettings()
    assert settings.tool_settings == {}


def test_save_tool_settings():
    """测试保存工具设置"""
    settings = AppSettings()
    settings.save_tool_settings("rect", {"color": "#ff0000", "width": 3})
    tool_settings = settings.get_tool_settings("rect")
    assert tool_settings["color"] == "#ff0000"
    assert tool_settings["width"] == 3
```

- [ ] **Step 4.2: 运行测试确认失败**

```bash
pytest tests/test_settings_memory.py -v
```

Expected: FAIL - AttributeError

- [ ] **Step 4.3: 扩展 AppSettings 类**

```python
# src/core/settings.py
# 在 @dataclass 装饰器下的 AppSettings 类中添加字段（约在第 48 行附近）

    # UX 优化配置
    # 颜色记忆
    recent_colors: list[str] = field(default_factory=list)
    max_recent_colors: int = 5
    
    # 工具设置记忆
    last_tool: str = "select"
    tool_settings: dict[str, dict] = field(default_factory=dict)
    
    # Toast 提示
    enable_toast: bool = True
    toast_duration: int = 2000
    
    # 快捷键帮助
    show_hotkey_tip: bool = True

# 在类的末尾添加方法：
    def add_recent_color(self, color: str) -> None:
        """添加颜色到最近使用列表"""
        # 去重：如果已存在则移除
        if color in self.recent_colors:
            self.recent_colors.remove(color)
        
        # 插入到开头
        self.recent_colors.insert(0, color)
        
        # 限制最多 5 个
        if len(self.recent_colors) > self.max_recent_colors:
            self.recent_colors = self.recent_colors[:self.max_recent_colors]
        
        self.save()
    
    def get_tool_settings(self, tool: str) -> dict:
        """获取工具设置"""
        return self.tool_settings.get(tool, {})
    
    def save_tool_settings(self, tool: str, settings: dict) -> None:
        """保存工具设置"""
        self.tool_settings[tool] = settings
        self.save()
```

- [ ] **Step 4.4: 运行测试确认通过**

```bash
pytest tests/test_settings_memory.py -v
```

Expected: 5 passed

- [ ] **Step 4.5: 提交配置扩展**

```bash
git add src/core/settings.py tests/test_settings_memory.py
git commit -m "feat: 扩展配置支持颜色记忆和工具设置

- 添加 recent_colors 列表（最多5个）
- 添加 tool_settings 字典（每个工具独立配置）
- 添加 add_recent_color 和 save_tool_settings 方法
- 添加单元测试

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 5: 工具栏颜色记忆 UI

**Files:**
- Modify: `src/overlay/toolbar.py`

- [ ] **Step 5.1: 修改颜色按钮生成逻辑**

```python
# src/overlay/toolbar.py
# 找到 _build_shape_menu 或颜色选择器相关的方法（约在第 200 行附近）
# 在颜色按钮生成部分，修改为：

from ..core.settings import get_settings

def _build_color_buttons(self, parent_layout):
    """构建颜色按钮，包括最近使用"""
    settings = get_settings()
    
    # 添加最近使用的颜色（最多3个）
    recent_count = 0
    for color in settings.recent_colors[:3]:
        btn = self._make_color_button(color, is_recent=True)
        btn.clicked.connect(lambda checked, c=color: self._on_color_selected(c))
        parent_layout.addWidget(btn)
        recent_count += 1
    
    # 如果有最近颜色，添加分隔线
    if recent_count > 0:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #ddd; max-width: 1px;")
        sep.setFixedWidth(1)
        parent_layout.addWidget(sep)
    
    # 添加预设颜色
    preset_colors = ["#ff3232", "#28a745", "#007bff", "#ffc107", "#000000"]
    for color in preset_colors:
        btn = self._make_color_button(color, is_recent=False)
        btn.clicked.connect(lambda checked, c=color: self._on_color_selected(c))
        parent_layout.addWidget(btn)
    
    # 添加取色器按钮
    picker_btn = QPushButton("+")
    picker_btn.setFixedSize(24, 24)
    picker_btn.clicked.connect(self._on_color_picker)
    parent_layout.addWidget(picker_btn)

def _make_color_button(self, color: str, is_recent: bool = False) -> QPushButton:
    """创建颜色按钮"""
    btn = QPushButton()
    btn.setFixedSize(24, 24)
    
    # 最近使用的颜色样式稍有不同
    if is_recent:
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                border: 1px solid #999;
                border-radius: 3px;
                opacity: 0.9;
            }}
            QPushButton:hover {{
                border: 2px solid #333;
            }}
        """)
    else:
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                border: 1px solid #ccc;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                border: 2px solid #333;
            }}
        """)
    
    return btn

def _on_color_selected(self, color: str):
    """颜色被选中"""
    self.overlay.current_color = QColor(color)
    
    # 添加到最近使用
    settings = get_settings()
    settings.add_recent_color(color)
    
    # 刷新颜色按钮（可选：重新生成按钮列表）
    # 这里简化处理，下次打开截图时会自动更新

def _on_color_picker(self):
    """打开取色器"""
    from PySide6.QtWidgets import QColorDialog
    color = QColorDialog.getColor()
    if color.isValid():
        self._on_color_selected(color.name())
```

- [ ] **Step 5.2: 手动测试颜色记忆**

测试步骤：
1. 运行 `python main.py`
2. 按 F12 截图
3. 选择一个颜色画图
4. 关闭截图
5. 再次截图 - 工具栏应显示刚才选择的颜色在最前面

预期：最近使用的颜色显示在前3个位置

- [ ] **Step 5.3: 提交颜色记忆 UI**

```bash
git add src/overlay/toolbar.py
git commit -m "feat: 工具栏添加颜色记忆功能

- 最近使用的3个颜色显示在工具栏前面
- 选择颜色后自动添加到最近列表
- 视觉区分最近颜色和预设颜色

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 6: 工具设置记忆

**Files:**
- Modify: `src/overlay/widget.py`
- Modify: `src/overlay/toolbar.py`

- [ ] **Step 6.1: 在 CaptureOverlay 初始化时恢复设置**

```python
# src/overlay/widget.py
# 在 __init__ 方法中，current_tool 和相关设置初始化部分（约在第 67 行）
# 修改为：

        s = get_settings()
        
        # 恢复上次使用的工具
        self.current_tool: str = s.last_tool if hasattr(s, 'last_tool') else "select"
        
        # 恢复工具设置
        tool_settings = s.get_tool_settings(self.current_tool) if hasattr(s, 'get_tool_settings') else {}
        self.current_color: QColor = QColor(tool_settings.get("color", s.default_color))
        self.current_width: int = tool_settings.get("width", s.default_line_width)
```

- [ ] **Step 6.2: 在切换工具时保存设置**

```python
# src/overlay/widget.py 或 src/overlay/toolbar.py
# 找到工具切换的方法（_set_tool 或类似）
# 添加保存逻辑：

def _set_tool(self, tool: str):
    """切换工具"""
    settings = get_settings()
    
    # 保存当前工具的设置
    if hasattr(settings, 'save_tool_settings'):
        current_settings = {
            "color": self.overlay.current_color.name(),
            "width": self.overlay.current_width,
        }
        settings.save_tool_settings(self.overlay.current_tool, current_settings)
        
        # 保存上次使用的工具
        settings.last_tool = tool
        settings.save()
    
    # 切换到新工具
    self.overlay.current_tool = tool
    
    # 恢复新工具的设置
    tool_settings = settings.get_tool_settings(tool)
    if tool_settings:
        self.overlay.current_color = QColor(tool_settings.get("color", "#ff3232"))
        self.overlay.current_width = tool_settings.get("width", 3)
```

- [ ] **Step 6.3: 在关闭覆盖层时保存设置**

```python
# src/overlay/widget.py
# 在 closeEvent 方法中添加（如果没有该方法则创建）

    def closeEvent(self, event):
        """关闭事件 - 保存当前工具设置"""
        settings = get_settings()
        
        if hasattr(settings, 'save_tool_settings'):
            current_settings = {
                "color": self.current_color.name(),
                "width": self.current_width,
            }
            settings.save_tool_settings(self.current_tool, current_settings)
        
        super().closeEvent(event)
```

- [ ] **Step 6.4: 手动测试工具设置记忆**

测试步骤：
1. 运行 `python main.py`
2. 按 F12 截图
3. 选择矩形工具，设置红色、粗细5
4. 关闭截图
5. 再次截图 - 应自动选中矩形工具，颜色红色，粗细5
6. 切换到画笔工具，设置蓝色、粗细3
7. 关闭截图
8. 再次截图 - 应自动选中画笔工具，颜色蓝色，粗细3

预期：每个工具的设置独立记忆

- [ ] **Step 6.5: 提交工具设置记忆**

```bash
git add src/overlay/widget.py src/overlay/toolbar.py
git commit -m "feat: 实现工具设置记忆功能

- 启动时恢复上次使用的工具
- 切换工具时保存/恢复工具设置
- 关闭截图时持久化当前设置
- 每个工具的颜色、粗细独立记忆

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 7: 截图历史管理

**Files:**
- Create: `src/core/screenshot_history.py`
- Create: `tests/test_screenshot_history.py`
- Modify: `src/overlay/actions.py`

- [ ] **Step 7.1: 编写历史管理测试**

```python
# tests/test_screenshot_history.py
import pytest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication
from src.core.screenshot_history import ScreenshotHistory


@pytest.fixture
def temp_history_dir():
    """创建临时历史目录"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def qapp():
    """Qt应用fixture"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_history_init(temp_history_dir, qapp):
    """测试历史管理初始化"""
    history = ScreenshotHistory(str(temp_history_dir))
    assert history.history_dir.exists()
    assert history.max_count == 100


def test_add_screenshot(temp_history_dir, qapp):
    """测试添加截图"""
    history = ScreenshotHistory(str(temp_history_dir))
    
    # 创建测试截图
    pixmap = QPixmap(100, 100)
    pixmap.fill()
    
    history.add_screenshot(pixmap, has_annotations=True)
    recent = history.get_recent(1)
    
    assert len(recent) == 1
    assert recent[0]["width"] == 100
    assert recent[0]["height"] == 100


def test_auto_cleanup(temp_history_dir, qapp):
    """测试自动清理"""
    history = ScreenshotHistory(str(temp_history_dir))
    history.max_count = 5
    
    # 添加6张截图
    pixmap = QPixmap(100, 100)
    for _ in range(6):
        history.add_screenshot(pixmap, False)
    
    # 应该只保留5张
    recent = history.get_recent(10)
    assert len(recent) == 5
```

- [ ] **Step 7.2: 运行测试确认失败**

```bash
pytest tests/test_screenshot_history.py -v
```

Expected: FAIL - ModuleNotFoundError

- [ ] **Step 7.3: 实现截图历史管理**

```python
# src/core/screenshot_history.py
import json
import time
from pathlib import Path
from datetime import datetime
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


class ScreenshotHistory:
    """截图历史管理"""
    
    def __init__(self, history_dir: str | None = None):
        if history_dir:
            self.history_dir = Path(history_dir)
        else:
            # 默认目录
            from pathlib import Path as P
            home = P.home()
            if home.exists():
                self.history_dir = home / ".config/MySnipaste/history"
            else:
                self.history_dir = Path("./screenshot_history")
        
        self.history_file = self.history_dir / "history.json"
        self.max_count = 100
        self._thumbnail_cache = {}
        
        # 创建目录
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载历史
        self._load_history()
    
    def _load_history(self):
        """加载历史记录"""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.screenshots = data.get("screenshots", [])
                    self.max_count = data.get("max_count", 100)
            except Exception:
                self.screenshots = []
        else:
            self.screenshots = []
    
    def _save_history(self):
        """保存历史记录"""
        data = {
            "screenshots": self.screenshots,
            "max_count": self.max_count,
        }
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add_screenshot(self, pixmap: QPixmap, has_annotations: bool):
        """添加截图到历史"""
        # 生成唯一ID（时间戳）
        timestamp = int(time.time())
        screenshot_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{screenshot_id}.png"
        
        # 保存截图文件
        file_path = self.history_dir / filename
        pixmap.save(str(file_path), "PNG")
        
        # 添加元数据
        meta = {
            "id": screenshot_id,
            "filename": filename,
            "timestamp": timestamp,
            "width": pixmap.width(),
            "height": pixmap.height(),
            "has_annotations": has_annotations,
        }
        self.screenshots.insert(0, meta)
        
        # 清理旧截图
        self._cleanup_old()
        
        # 保存历史
        self._save_history()
    
    def _cleanup_old(self):
        """清理旧截图"""
        while len(self.screenshots) > self.max_count:
            old = self.screenshots.pop()
            # 删除文件
            file_path = self.history_dir / old["filename"]
            if file_path.exists():
                file_path.unlink()
    
    def get_recent(self, count: int = 10) -> list[dict]:
        """获取最近的截图"""
        recent = self.screenshots[:count]
        
        # 添加相对时间
        for item in recent:
            item["time_ago"] = self._format_time_ago(item["timestamp"])
        
        return recent
    
    def _format_time_ago(self, timestamp: int) -> str:
        """格式化相对时间"""
        now = int(time.time())
        diff = now - timestamp
        
        if diff < 60:
            return "刚才"
        elif diff < 3600:
            return f"{diff // 60} 分钟前"
        elif diff < 86400:
            return f"{diff // 3600} 小时前"
        else:
            return f"{diff // 86400} 天前"
    
    def get_thumbnail(self, screenshot_id: str, size=(48, 36)) -> QPixmap:
        """获取缩略图（带缓存）"""
        cache_key = f"{screenshot_id}_{size[0]}x{size[1]}"
        
        if cache_key in self._thumbnail_cache:
            return self._thumbnail_cache[cache_key]
        
        # 查找截图
        meta = next((s for s in self.screenshots if s["id"] == screenshot_id), None)
        if not meta:
            return QPixmap()
        
        # 加载并缩放
        file_path = self.history_dir / meta["filename"]
        if not file_path.exists():
            return QPixmap()
        
        pixmap = QPixmap(str(file_path))
        thumbnail = pixmap.scaled(size[0], size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # 缓存
        self._thumbnail_cache[cache_key] = thumbnail
        
        return thumbnail
    
    def delete_screenshot(self, screenshot_id: str):
        """从历史中删除"""
        meta = next((s for s in self.screenshots if s["id"] == screenshot_id), None)
        if meta:
            self.screenshots.remove(meta)
            
            # 删除文件
            file_path = self.history_dir / meta["filename"]
            if file_path.exists():
                file_path.unlink()
            
            self._save_history()
```

- [ ] **Step 7.4: 运行测试确认通过**

```bash
pytest tests/test_screenshot_history.py -v
```

Expected: 3 passed

- [ ] **Step 7.5: 提交历史管理核心**

```bash
git add src/core/screenshot_history.py tests/test_screenshot_history.py
git commit -m "feat: 实现截图历史管理核心

- 添加 ScreenshotHistory 类（保存、加载、清理）
- 支持最多100张截图自动清理
- 缩略图生成和缓存
- 相对时间格式化
- 添加单元测试

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 8: 集成历史保存到操作流程

**Files:**
- Modify: `src/overlay/actions.py`
- Modify: `src/core/settings.py`

- [ ] **Step 8.1: 在配置中添加历史功能开关**

```python
# src/core/settings.py
# 在 AppSettings 类中添加字段：

    # 截图历史
    enable_history: bool = True
    history_max_count: int = 100
    auto_save_to_history: bool = True
```

- [ ] **Step 8.2: 在保存/复制操作后保存到历史**

```python
# src/overlay/actions.py
# 在文件顶部添加导入
from ..core.screenshot_history import ScreenshotHistory

# 在 _on_copy_action 方法中，QApplication.clipboard().setPixmap() 之后添加：
    # 保存到历史
    settings = get_settings()
    if hasattr(settings, 'enable_history') and settings.enable_history:
        history = ScreenshotHistory()
        has_annotations = len(self.annotations) > 0
        history.add_screenshot(result_pixmap, has_annotations)

# 在 _on_save_action 方法中，保存文件成功后添加同样的逻辑
```

- [ ] **Step 8.3: 手动测试历史保存**

测试步骤：
1. 运行 `python main.py`
2. 截图并复制
3. 检查 `~/.config/MySnipaste/history/` 目录
4. 应该有一个 `.png` 文件和 `history.json`

预期：截图自动保存到历史目录

- [ ] **Step 8.4: 提交历史保存集成**

```bash
git add src/overlay/actions.py src/core/settings.py
git commit -m "feat: 集成历史保存到操作流程

- 复制/保存截图后自动保存到历史
- 添加历史功能开关配置
- 记录是否有标注

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 9: 托盘菜单历史列表

**Files:**
- Modify: `src/ui/tray.py`

- [ ] **Step 9.1: 在托盘菜单添加历史子菜单**

```python
# src/ui/tray.py
# 在文件顶部添加导入
from ..core.screenshot_history import ScreenshotHistory

# 在 setup 方法中，添加历史菜单（约在第 47 行，OCR 菜单之后）

        # 历史截图子菜单
        history_menu = QMenu(_("Recent Screenshots"), self.app)
        self._build_history_menu(history_menu)
        menu.addMenu(history_menu)
        menu.addSeparator()

# 添加构建历史菜单的方法（在类的末尾）
    def _build_history_menu(self, menu: QMenu):
        """构建历史截图子菜单"""
        history = ScreenshotHistory()
        recent = history.get_recent(10)
        
        if not recent:
            no_history = QAction(_("No recent screenshots"), self.app)
            no_history.setEnabled(False)
            menu.addAction(no_history)
            return
        
        for item in recent:
            # 创建菜单项：时间 - 尺寸
            text = f"{item['time_ago']} - {item['width']}×{item['height']}"
            action = QAction(text, self.app)
            
            # 绑定点击事件
            screenshot_id = item['id']
            action.triggered.connect(lambda checked, sid=screenshot_id: self._on_history_click(sid))
            
            menu.addAction(action)
    
    def _on_history_click(self, screenshot_id: str):
        """点击历史截图项"""
        history = ScreenshotHistory()
        
        # 查找截图
        meta = next((s for s in history.screenshots if s["id"] == screenshot_id), None)
        if not meta:
            return
        
        # 加载截图
        from pathlib import Path
        file_path = history.history_dir / meta["filename"]
        if not file_path.exists():
            return
        
        from PySide6.QtGui import QPixmap
        pixmap = QPixmap(str(file_path))
        
        # 复制到剪贴板
        QApplication.clipboard().setPixmap(pixmap)
        
        # 显示 Toast（如果在截图界面）
        from ..ui.toast import ToastManager
        ToastManager.show(_("Copied from history"), "✓", "success")
```

- [ ] **Step 9.2: 添加历史菜单翻译**

```json
// src/resources/locales/zh_CN.json
// 添加：
{
  "Recent Screenshots": "最近截图",
  "No recent screenshots": "暂无历史截图",
  "Copied from history": "已从历史复制"
}
```

- [ ] **Step 9.3: 手动测试历史菜单**

测试步骤：
1. 先截图几次
2. 右键点击托盘图标
3. 应该看到"最近截图"菜单
4. 展开应显示最近的截图列表
5. 点击任意一项 - 应复制到剪贴板并显示提示

预期：历史列表正确显示，点击可复制

- [ ] **Step 9.4: 提交托盘历史菜单**

```bash
git add src/ui/tray.py src/resources/locales/zh_CN.json
git commit -m "feat: 托盘菜单添加历史截图列表

- 添加"最近截图"子菜单
- 显示最近10张截图（时间、尺寸）
- 点击可复制到剪贴板
- 添加中文翻译

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 10: 完善和测试

**Files:**
- Modify: `src/resources/locales/en_US.json` (如果存在)
- Update: `README.md` (可选)

- [ ] **Step 10.1: 添加英文翻译（如果有英文语言包）**

```json
// src/resources/locales/en_US.json
{
  "Copied to clipboard": "Copied to clipboard",
  "Screenshot saved": "Screenshot saved",
  "Pinned to desktop": "Pinned to desktop",
  "Undone": "Undone",
  "Redone": "Redone",
  "OCR recognizing...": "OCR recognizing...",
  "Recognition complete": "Recognition complete",
  "Hotkeys": "Hotkeys",
  "Copy": "Copy",
  "Save": "Save",
  "Pin": "Pin",
  "Undo": "Undo",
  "Redo": "Redo",
  "Toggle help": "Toggle help",
  "Press Esc to close": "Press Esc to close",
  "Recent Screenshots": "Recent Screenshots",
  "No recent screenshots": "No recent screenshots",
  "Copied from history": "Copied from history"
}
```

- [ ] **Step 10.2: 运行所有测试**

```bash
pytest tests/ -v
```

Expected: 所有测试通过

- [ ] **Step 10.3: 完整功能测试**

测试所有功能：

**Toast 提示**:
- [ ] 复制截图显示"已复制到剪贴板"
- [ ] 保存截图显示"截图已保存"
- [ ] 贴图显示"已固定到桌面"
- [ ] 撤销显示"已撤销"
- [ ] 重做显示"已重做"
- [ ] Toast 在顶部居中显示
- [ ] Toast 2秒后自动消失
- [ ] 鼠标悬停 Toast 暂停消失

**快捷键帮助**:
- [ ] 按 ? 显示帮助面板
- [ ] 面板显示所有快捷键
- [ ] 按 Esc 或再按 ? 关闭面板

**颜色记忆**:
- [ ] 选择颜色后，下次截图显示在前面
- [ ] 最多显示3个最近颜色
- [ ] 选择自定义颜色也会记忆

**工具设置记忆**:
- [ ] 矩形工具的颜色和粗细独立记忆
- [ ] 画笔工具的颜色和粗细独立记忆
- [ ] 切换工具时自动恢复上次设置

**历史列表**:
- [ ] 截图后自动保存到历史
- [ ] 托盘菜单显示"最近截图"
- [ ] 列表显示最近10张
- [ ] 点击可复制到剪贴板

- [ ] **Step 10.4: 更新 README（可选）**

如果需要，在 README.md 中添加新功能说明：

```markdown
## 新功能

### 视觉反馈
- 所有操作（复制、保存、贴图等）都有即时提示
- 按 ? 或 F1 查看快捷键帮助

### 智能记忆
- 自动记住最近使用的3个颜色
- 每个工具的设置独立记忆（颜色、粗细等）

### 历史管理
- 自动保存最近100张截图
- 托盘菜单快速访问历史截图
```

- [ ] **Step 10.5: 最终提交**

```bash
git add src/resources/locales/en_US.json README.md
git commit -m "docs: 添加英文翻译和功能说明

- 添加所有新功能的英文翻译
- 更新 README 说明新功能
- 完成 UX 快速优化实施

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## 验证清单

完成所有任务后，验证以下功能：

### 功能验证
- [ ] Toast 提示系统正常工作（5种场景）
- [ ] 快捷键帮助面板正常显示
- [ ] 颜色记忆功能正常
- [ ] 工具设置记忆功能正常
- [ ] 历史截图保存和访问正常

### 代码质量
- [ ] 所有单元测试通过
- [ ] 代码遵循 DRY 原则
- [ ] 没有明显的性能问题
- [ ] 翻译完整（中英文）

### 文档
- [ ] 代码有适当的注释
- [ ] README 已更新（如需要）
- [ ] 提交信息清晰

---

## 预期工时

- Task 1-2: Toast 系统 → 2-3 小时
- Task 3: 快捷键帮助 → 1-2 小时
- Task 4-6: 颜色和工具记忆 → 2-3 小时
- Task 7-9: 历史管理 → 3-4 小时
- Task 10: 完善测试 → 1-2 小时

**总计**: 9-14 小时（约 1-2 个工作日）

---

## 注意事项

1. **测试驱动**: 每个功能都先写测试
2. **频繁提交**: 每完成一个小功能就提交
3. **DRY 原则**: 避免重复代码，提取公共方法
4. **YAGNI 原则**: 只实现设计中要求的功能
5. **向后兼容**: 新配置字段提供默认值
6. **错误处理**: 文件操作添加 try-except
7. **性能**: Toast 动画使用 QPropertyAnimation
8. **国际化**: 所有用户可见文本使用 _() 函数