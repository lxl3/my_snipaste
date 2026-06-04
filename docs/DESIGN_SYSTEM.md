# MySnipaste 设计系统

> 最后更新: 2026-06-04
> 负责人: 开发团队
> 目的: 统一视觉语言，提升开发效率，确保体验一致

---

## 一、设计原则

1. **一致性优先** - 相同场景使用相同组件
2. **主题响应** - 所有 UI 自动适配亮色/暗色模式
3. **参数化设计** - 组件支持自定义但有合理默认值
4. **生命周期管理** - 组件销毁时正确清理资源

---

## 二、核心模块

### `core/qss_base.py` - 样式基础库

所有通用组件的 QSS 样式集中管理，避免重复代码。

**使用方式**：
```python
from ..core import qss_base

# 使用默认样式
btn.setStyleSheet(qss_base.pushbutton_qss())

# 自定义参数
btn.setStyleSheet(qss_base.pushbutton_qss(
    padding="8px 16px",
    border_radius="6px"
))
```

**已提供组件**：
- `pushbutton_qss()` - 按钮
- `lineedit_qss()` - 单行输入框
- `combobox_qss()` - 下拉框
- `spinbox_qss()` - 数字输入框
- `checkbox_qss()` - 复选框
- `groupbox_qss()` - 分组框
- `slider_qss()` - 滑块
- `scrollbar_qss()` - 滚动条
- `menu_qss()` - 菜单
- `label_qss()` - 标签

### `ui/title_bar.py` - 标题栏组件

统一的无边框窗口标题栏，支持拖拽和主题响应。

**使用方式**：
```python
from ..ui.title_bar import TitleBar

title_bar = TitleBar(self, _("Settings"))
layout.addWidget(title_bar, 0, 0)
```

**参数**：
- `title` - 标题文字
- `show_minimize` - 是否显示最小化按钮（默认 True）
- `height` - 标题栏高度（默认 32px）
- `title_size` - 标题字号（默认 13px）
- `close_size` - 按钮尺寸（默认 32px）

---

## 三、设计规范

### 间距系统

```python
SPACING = {
    'xs': 2,   # 最小间距 - 同类元素内部
    'sm': 4,   # 小间距 - 相关元素之间
    'md': 8,   # 中等间距 - 内容区域 padding
    'lg': 12,  # 大间距 - 分组之间
    'xl': 16,  # 超大间距 - 章节之间
}
```

**使用场景**：
- QHBoxLayout/QVBoxLayout 的 spacing
- widget 的 setContentsMargins
- QSS 中的 padding/margin

### 圆角规范

```python
RADIUS = {
    'none': 0,   # 无圆角 - 子菜单、弹窗边缘
    'sm': 2,     # 小圆角 - 输入框、小按钮
    'md': 4,     # 中等圆角 - 普通按钮、菜单项
    'lg': 6,     # 大圆角 - 卡片、对话框
}
```

### 尺寸规范

```python
BUTTON_SIZE = {
    'sm': 18,   # 小按钮 - 颜色选择器、工具按钮
    'md': 24,   # 中等按钮 - 普通功能按钮
    'lg': 32,   # 大按钮 - 主要操作按钮
}

INPUT_HEIGHT = {
    'sm': 24,   # 小输入框 - 紧凑布局
    'md': 32,   # 中等输入框 - 标准表单
    'lg': 40,   # 大输入框 - 突出表单
}
```

### 颜色 Token（由 theme.py 提供）

**背景色**：
- `$bg_primary` - 主背景
- `$bg_secondary` - 次要背景
- `$bg_menu` - 菜单背景
- `$bg_input` - 输入框背景
- `$bg_toolbar` - 工具栏背景（半透明）

**文字色**：
- `$text_primary` - 主要文字
- `$text_secondary` - 次要文字
- `$text_disabled` - 禁用文字
- `$text_placeholder` - 占位符
- `$text_accent` - 强调文字（accent 背景上的文字）

**交互色**：
- `$accent` - 强调色（蓝色）
- `$hover_bg` - 悬停背景
- `$border` - 边框色
- `$border_light` - 浅边框

---

## 四、组件使用指南

### 对话框标准布局

```python
class MyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 标题栏
        title_bar = TitleBar(self, _("My Dialog"), show_minimize=False)
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 16)
        content_layout.setSpacing(12)
        # ... 添加内容 ...
        main_layout.addWidget(content)
```

### 表单输入标准

```python
# 标签 + 输入框
label = QLabel(_("Name:"))
label.setStyleSheet(qss_base.label_qss(font_weight="500"))

input_field = QLineEdit()
input_field.setFixedHeight(32)  # INPUT_HEIGHT['md']
input_field.setStyleSheet(qss_base.lineedit_qss())

layout.addWidget(label)
layout.addWidget(input_field)
```

### 按钮组标准

```python
# 主要按钮 + 次要按钮
btn_layout = QHBoxLayout()
btn_layout.addStretch()

cancel_btn = QPushButton(_("Cancel"))
cancel_btn.setFixedHeight(32)
cancel_btn.setStyleSheet(qss_base.pushbutton_qss(
    bg="$bg_secondary"
))

ok_btn = QPushButton(_("OK"))
ok_btn.setFixedHeight(32)
ok_btn.setStyleSheet(qss_base.pushbutton_qss(
    bg="$accent",
    color="$text_accent",
    font_weight="500"
))

btn_layout.addWidget(cancel_btn)
btn_layout.addWidget(ok_btn)
```

---

## 五、迁移清单

### 已迁移 ✅
- [x] pin_window.py - 使用 qss_base.menu_qss()
- [x] title_bar.py - 新建统一组件

### 待迁移 ⚠️
- [ ] settings_dialog.py - 迁移到 qss_base + TitleBar
- [ ] tray.py - 使用 qss_base.menu_qss()
- [ ] overlay/toolbar.py - 迁移控件样式到 qss_base
- [ ] ui/toast.py - 统一样式函数
- [ ] ui/ocr_dialog.py - 统一样式函数

### 新功能开发规范 📋
- 所有新对话框必须使用 TitleBar 组件
- 所有新按钮必须使用 qss_base.pushbutton_qss()
- 所有新输入框必须使用 qss_base.lineedit_qss()
- 新增通用样式需求应添加到 qss_base.py

---

## 六、常见问题

### Q: 如何自定义按钮样式？
A: 优先使用 qss_base 参数自定义，避免完全重写 QSS：
```python
# ✅ 推荐
btn.setStyleSheet(qss_base.pushbutton_qss(
    padding="10px 24px",
    border_radius="8px"
))

# ❌ 不推荐（除非有特殊需求）
btn.setStyleSheet("QPushButton { ... 完全自定义 ... }")
```

### Q: 如何确保主题响应？
A: 组件应监听 theme_changed 信号并刷新样式：
```python
from ..core.theme import theme as _theme

def __init__(self):
    # ... 初始化 ...
    self._refresh_style()
    _theme.theme_changed.connect(self._on_theme_changed)

def _refresh_style(self):
    self.btn.setStyleSheet(qss_base.pushbutton_qss())

def _on_theme_changed(self, mode: str):
    self._refresh_style()

def destroy(self):
    _theme.theme_changed.disconnect(self._on_theme_changed)
    super().destroy()
```

### Q: 什么时候可以不用 qss_base？
A: 仅在以下情况：
1. 需要复杂的伪类选择器（qss_base 不支持）
2. 需要多重嵌套选择器（如 "QDialog QGroupBox QPushButton"）
3. 样式高度定制且不可复用

---

*此文档持续更新，每次新增组件或规范请同步修改。*
