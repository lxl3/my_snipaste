---
name: frontend-design
description: "Use when styling PySide6/Qt6 widget UIs, implementing dark/light theme switching, writing QSS (Qt Style Sheets), fixing theme adaptation bugs, or designing dialog/window layouts for this project. Triggers: 'theme', 'QSS', 'dark mode', 'light mode', 'styling', 'UI design', '暗色模式', '主题切换', '样式'."
---

# PySide6/Qt6 Frontend Design for MySnipaste

## Overview

This project uses a **token-based theming system** (`ThemeManager`) with `QSS` (Qt Style Sheets) for all UI styling. Every color comes from named tokens (`$bg_primary`, `$accent`, etc.) — never hardcode hex values.

Two parallel styling mechanisms exist, and **QSS should be preferred**:

| Mechanism | When to Use |
|-----------|-------------|
| **QSS** (`_theme.qss()`) | Widget backgrounds, borders, text colors, hover/selected states, padding — everything visual |
| **QPalette** (`_theme.apply_to_widget()`) | Only as fallback when QSS can't reach a widget (e.g. viewport of QScrollArea, native sub-controls) |

## Theme System

### Import

```python
from ..core.theme import theme as _theme          # settings_dialog style
from ..core.theme import theme as theme_mgr         # tray style (existing convention)
# Both point to the same singleton — pick whichever matches the file's convention
```

### Token Reference

**Backgrounds:**
| Token | Usage |
|-------|-------|
| `$bg_primary` | Main background (dialogs, tab pages, content areas) |
| `$bg_secondary` | Secondary background (hover rows, alt rows, TitleBar) |
| `$bg_input` | Input field background (QLineEdit, QSpinBox, QComboBox) |
| `$bg_menu` | Menu/popup background (QMenu) |
| `$bg_toolbar` | Toolbar background (capture toolbar) |
| `$bg_toolbar_alt` | Submenu/toolbar alt background |
| `$bg_overlay` | Semi-transparent overlay mask |

**Text:**
| Token | Usage |
|-------|-------|
| `$text_primary` | Primary text color |
| `$text_secondary` | Secondary/helper text |
| `$text_placeholder` | Placeholder text |
| `$text_accent` | Text on accent-colored backgrounds |
| `$text_disabled` | Disabled state text |

**Borders:**
| Token | Usage |
|-------|-------|
| `$border` | Regular borders (group boxes, widget frames) |
| `$border_light` | Light dividers/separators |
| `$border_focus` | Focus highlight border |
| `$border_input` | Input field borders |

**Accent:**
| Token | Usage |
|-------|-------|
| `$accent` | Primary accent (selected tab, checkbox checked, button primary) |
| `$accent_hover` | Accent hover state |
| `$accent_disabled` | Accent disabled state |
| `$hover_bg` | Generic hover background |

**Special:**
| Token | Usage |
|-------|-------|
| `$hotkey_conflict` | Conflict warning text color |
| `$shadow` | Drop shadow color |
| `$toolbar_shadow` | Toolbar-specific shadow |

→ Full list: `src/core/theme.py` lines 23-66 (all `XXX = "token_name"` constants)

### API

```python
# Get raw color value
color = _theme.get("bg_primary")          # → "#1E1E1E"

# Build QSS string with token substitution
qss = _theme.qss("background: $bg_primary; color: $text_primary;")
# → "background: #1E1E1E; color: #CCCCCC;"
# (8-digit #RRGGBBAA hex is auto-converted to rgba())

# Apply palette to a single widget
_theme.apply_to_widget(widget)
# This sets widget.setPalette(palette) — use only when QSS isn't enough

# Check current mode
_theme.is_dark()                          # → True/False
_theme.resolved                           # → "light" or "dark"
_theme.mode                               # → "light", "dark", or "system"

# Listen for theme changes
_theme.theme_changed.connect(self._on_theme_changed)
```

## QSS Patterns

### Basic Rule: Always use `_theme.qss()`

```python
# ✅ CORRECT — tokens are theme-aware
self.setStyleSheet(_theme.qss("""
    QPushButton {
        background: $bg_secondary;
        color: $text_primary;
        border: 1px solid $border;
    }
"""))

# ❌ WRONG — hardcoded hex breaks dark mode
self.setStyleSheet("""
    QPushButton {
        background: #F5F5F5;
        color: #333333;
    }
""")
```

### QSS Background Control (IMPORTANT)

**Use `background: $bg_primary` in QSS, NOT `setAutoFillBackground(True)`.**

`autoFillBackground` fills with `palette().window()` DOMINATING any QSS — it produces stale colors when switching themes because hidden widgets (QStackedWidget children) don't repaint.

```python
# ✅ CORRECT — QSS controls all backgrounds
widget.setAttribute(Qt.WA_StyledBackground)
# NO setAutoFillBackground(True) — let QSS do it

# ❌ WRONG — autoFillBackground conflicts with QSS
widget.setAutoFillBackground(True)  # palette overrides QSS on repaint
```

### Complete Widget Coverage for Theme Switching

When a container widget has children, every level must have explicit QSS background:

```css
/* ❌ INCOMPLETE — children without background show old palette */
QTabWidget { background: $bg_primary; }

/* ✅ COMPLETE — every structural level covered */
QTabWidget { background: $bg_primary; }
QTabBar { background: $bg_primary; }
QTabWidget::pane { background: $bg_primary; }
QTabWidget QStackedWidget { background: $bg_primary; }
QTabWidget QStackedWidget > QWidget { background: $bg_primary; }
```

### Dynamic Widgets (QSS on individual widgets)

For widgets that need per-instance QSS (not inherited from parent), use `_add_themed_widget()` pattern:

```python
# Register widget for theme re-application
def _add_themed_widget(self, widget, style_template):
    self._themed_widgets.append((widget, style_template))
    widget.setStyleSheet(_theme.qss(style_template))

# On theme change, re-apply
def _on_theme_changed(self, mode):
    for widget, template in self._themed_widgets:
        widget.setStyleSheet(_theme.qss(template))
```

## Theme Switching Pattern

Every dialog/widget that supports live theme switching must follow this structure:

```python
def __init__(self):
    self._themed_widgets = []
    self._build_ui()
    _theme.theme_changed.connect(self._on_theme_changed)

def _on_theme_changed(self, mode):
    # 1. Apply palette (fallback, for widgets QSS can't reach)
    _theme.apply_to_widget(self)
    
    # 2. Clear + rebuild QSS
    self.setStyleSheet("")
    self._build_stylesheet_qss()
    
    # 3. Re-apply dynamic widget styles
    for widget, template in self._themed_widgets:
        widget.setStyleSheet(_theme.qss(template))
    
    # 4. Force polish all children
    for w in [self] + self.findChildren(QWidget):
        w.style().unpolish(w)
        w.style().polish(w)
    
    # 5. Special: QScrollArea viewport needs explicit QSS
    for sa in self.findChildren(QScrollArea):
        vp = sa.viewport()
        vp.setStyleSheet(_theme.qss("background: $bg_primary;"))
        vp.style().unpolish(vp)
        vp.style().polish(vp)
    
    # 6. Force repaint
    self.update()
```

### Special: QTabBar palette

`QTabBar` is an internal child of `QTabWidget`. Setting palette on the parent does NOT propagate:

```python
# MUST do this in _on_theme_changed:
_tab_bar = self._tabs.findChild(QTabBar)
if _tab_bar:
    _theme.apply_to_widget(_tab_bar)
```

## Window Styling

### Frameless Windows

This project uses `FramelessWindowHint` for all dialogs (not DWM dark title bar API):

```python
self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
```

Each frameless window needs a custom `TitleBar` widget (see `src/ui/settings_dialog.py:TitleBar`):
- Drag support: `mousePressEvent`/`mouseMoveEvent`/`mouseReleaseEvent`
- Minimize button: `parent.showMinimized()`
- Close button: `parent.close()`
- QSS via `_theme.qss()` in the parent's `_build_stylesheet_qss()`

### TitleBar QSS Pattern

```css
TitleBar {
    background: $bg_secondary;
    border-bottom: 1px solid $border;
}
TitleBar QLabel {
    color: $text_primary;
    font-size: 13px;
    font-weight: 600;
}
TitleBar QPushButton {
    background: transparent;
    border: none;
    color: $text_primary;
}
TitleBar QPushButton:hover { background: $hover_bg; }
TitleBar QPushButton:pressed { background: $accent; color: $text_accent; }
```

## Common Widget Styling

### QGroupBox
```css
QGroupBox {
    border: 1px solid $border;
    border-radius: 6px;
    margin-top: 12px;
    padding: 16px 12px 12px;
    background: transparent;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: $text_primary;
}
```

### QPushButton
```css
QPushButton {
    padding: 6px 20px;
    border: 1px solid $border;
    border-radius: 4px;
    background: $bg_secondary;
    color: $text_primary;
}
QPushButton:hover { background: $hover_bg; }
QPushButton:pressed { background: $bg_primary; }
```

### QLineEdit / QSpinBox
```css
QLineEdit, QSpinBox {
    padding: 4px 8px;
    border: 1px solid $border;
    border-radius: 4px;
    background: $bg_input;
    color: $text_primary;
}
QLineEdit:focus { border-color: $accent; }
```

### QComboBox
```css
QComboBox {
    padding: 4px 8px;
    border: 1px solid $border;
    border-radius: 4px;
    background: $bg_input;
    color: $text_primary;
}
QComboBox::drop-down { border: none; }
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid $text_primary;
}
QComboBox QAbstractItemView {
    background: $bg_input;
    color: $text_primary;
    selection-background-color: $accent;
    selection-color: $text_accent;
}
```

### QCheckBox
```css
QCheckBox { color: $text_primary; }
QCheckBox::indicator { width: 16px; height: 16px; }
QCheckBox::indicator:unchecked {
    border: 1px solid $border;
    border-radius: 3px;
    background: $bg_input;
}
QCheckBox::indicator:checked {
    border: 1px solid $accent;
    border-radius: 3px;
    background: $accent;
}
```

### QSlider
```css
QSlider::groove:horizontal { height: 6px; background: $border; border-radius: 3px; }
QSlider::handle:horizontal {
    background: $accent;
    width: 14px; height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QSlider::sub-page:horizontal { background: $accent; border-radius: 3px; }
```

### QScrollBar (vertical)
```css
QScrollBar:vertical {
    width: 8px;
    background: transparent;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: $border;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    border: none;
}
```

### QMenu (system tray)
```css
QMenu {
    background: $bg_menu;
    border: 1px solid $border;
    padding: 4px;
}
QMenu::item {
    padding: 6px 8px 6px 6px;
    color: $text_primary;
}
QMenu::item:selected {
    background: $accent;
    color: $text_accent;
}
QMenu::separator {
    height: 1px;
    background: $border;
    margin: 4px 8px;
}
QMenu::icon { padding-left: 4px; }
```

## Anti-Patterns

| Anti-Pattern | Why It's Wrong | Fix |
|-------------|----------------|-----|
| `setAutoFillBackground(True)` on QWidget | Palette overrides QSS; hidden QStackedWidget children don't repaint on theme switch | Remove autoFillBackground; add explicit `QSS background: $bg_primary` |
| `setStyleSheet("...")` without `_theme.qss()` | Hardcoded hex breaks dark mode | Always use `_theme.qss("...")` |
| `QPalette` for styling instead of QSS | Palette is a fallback; QSS is more reliable for theme switching | Use QSS first; palette only for widgets QSS can't reach |
| `#RRGGBBAA` directly in QSS | QSS doesn't support 8-digit hex — silently fails | Always use `_theme.qss()` which auto-converts to rgba() |
| Setting `app.setStyleSheet()` | Breaks `WA_TranslucentBackground` windows (known Qt6 bug) | Never call this; use per-widget QSS instead |
| Relying on `QSS` cascade to reach QTabBar | QTabBar is a separate child widget, not covered by parent QSS | Add explicit `QTabBar { background: ... }` rule + `findChild(QTabBar).setPalette()` |
| Calling `apply_dark_title_bar()` | Unreliable across Windows builds; DWM API may not work | Use `FramelessWindowHint` + custom `TitleBar` widget instead |
| Adding emojis to source code without `create_emoji_icon()` | QAction text with emoji renders inconsistently across platforms | Use `QAction(create_emoji_icon("🔧"), "text", parent)` |
| Using `QMessageBox` for custom dialogs | Can't theme properly; native title bar breaks dark mode | Use `QDialog` + `FramelessWindowHint` + custom `TitleBar` |

## Testing Theme Changes

When implementing or fixing theme adaptation:

1. **Switch themes while dialog is open** — stay in the dialog and change the theme combo
2. **Check every tab** — switch to each tab; hidden QStackedWidget pages often miss updates
3. **Check every sub-widget** — QScrollArea viewports, QTabBar, QComboBox dropdowns
4. **Check frameless windowTitleBar buttons** — hover/pressed states use `$hover_bg`/`$accent`
5. **Verify QSS token substitution** — look for `#RRGGBBAA` being auto-converted to `rgba()`

## Quick Reference

```
Theme import:      from ..core.theme import theme as _theme
Build QSS:         _theme.qss("background: $bg_primary;")
Get token:         _theme.get("bg_primary")
Apply palette:     _theme.apply_to_widget(widget)
Check dark:        _theme.is_dark()
Listen changes:    _theme.theme_changed.connect(handler)
StyledBackground:  widget.setAttribute(Qt.WA_StyledBackground)
Frameless window:  widget.setWindowFlags(widget.windowFlags() | Qt.FramelessWindowHint)
Find tab bar:      self._tabs.findChild(QTabBar)
Emoji icon:        create_emoji_icon("📸")
```
