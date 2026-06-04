# 会话完成功能清单

日期: 2026-06-02

---

## 1. 标注编辑功能（选区交互）

| 功能 | 验证步骤 |
|------|----------|
| 标注选中 | F12截图 → 画一个矩形/箭头 → 鼠标移动到标注边框附近 → 出现蓝色选中框+白色手柄 |
| 标注拖动 | 选中标注后按住并拖动 → 标注跟随移动 |
| 标注缩放 | 选中标注后拖拽 8 个白色手柄（4 角 + 4 边中点）→ 标注缩放 |
| 标注删除 | 选中标注 → 按 Delete / Backspace |
| 文字重新编辑 | 双击已存在的文字标注 → 进入编辑模式 |
| 撤销/重做 | Ctrl+Z 撤销 / Ctrl+Y 重做 |

## 2. 黑屏修复

**根因**: Qt6 的 `QColor("rgba(0,0,0,140)")` 将 alpha 按 0.0-1.0 CSS 规范解析，值 140 > 1.0 → 钳位到 255 → 完全不透明。

**改动文件**:
- `src/core/theme.py` — 所有 `rgba()` token 改为 `#RRGGBBAA` hex 格式
- `src/core/theme.py` — 移除 `apply_to_app()` 中的 `app.setStyleSheet("")`（已知会破坏 `WA_TranslucentBackground`）
- `src/overlay/widget.py` — 关键颜色使用 `QColor(r,g,b,a)` 整数构造器替代字符串解析
- `src/overlay/widget.py` — paintEvent 包裹 try/except + 诊断日志

**验证**: F12截图 → 覆盖层应该是半透明的（能透过覆盖层看到桌面）→ 截图区域不黑。

## 3. 工具栏毛玻璃效果 + 入场动画

**改动文件**: `src/overlay/toolbar.py`, `src/overlay/widget.py`

### 3.1 毛玻璃渐变背景
- 自动从主题色 `bg_toolbar` 解析 RGBA，生成 `qlineargradient`（顶部 +25 alpha 模拟玻璃反光，底部 -15 alpha）
- 半透明白色顶部高光 `border-top: rgba(255,255,255,160)`
- 底部轻微阴影 `border-bottom: rgba(128,128,128,30)`
- 解析失败时回退到纯色 `$bg_toolbar`

### 3.2 入场淡入动画
- 工具栏出现时 150ms `QGraphicsOpacityEffect` + `QPropertyAnimation` 从 0→1 透明度
- 动画完成后自动清除 `QGraphicsOpacityEffect`
- 修复了 PySide6 GC 导致动画从未启动的 bug（通过 `self._anim` 持有引用）

### 3.3 按钮交互
- hover: 浅灰背景 `rgba(128,128,128,25)` + 1px 边框
- checked: 主题色 `$accent` 背景
- pressed: 更深灰背景 `rgba(128,128,128,45)`
- 子菜单按钮同步更新匹配

**验证**: 截图后工具栏出现 → 背景半透明渐变（顶部稍亮）→ 顶部有白色高光线 → 150ms 淡入 → 按钮悬停/选中/按下各有不同样式。

## 4. 设置对话框崩溃修复

| 修复 | 文件 | 行 |
|------|------|----|
| `QComboBox.currentDataChanged` → `currentIndexChanged` | `src/ui/settings_dialog.py` | 316 |
| 添加 `QApplication` 到 import | `src/ui/settings_dialog.py` | 6 |

**验证**: 菜单 → 设置 → 切换主题下拉框 → 不再报错，主题实时切换。

## 5. 主题 QSS 兼容性

**改动文件**: `src/core/theme.py`

`ThemeManager.qss()` 方法自动识别 `#RRGGBBAA`（9 位 hex）并转换为 `rgba(r,g,b,a)` 格式，因为 Qt QSS 不支持 8 位 hex 颜色。

**验证**: 所有使用 `_t.qss()` 的 QSS（工具栏、子菜单、分隔线、各种弹出菜单）颜色显示正常，包括半透明色。

---

## 主要改动文件汇总

| 文件 | 改动 |
|------|------|
| `src/core/theme.py` | token hex 格式化、qss() hex→rgba 转换、移除 setStyleSheet("") |
| `src/overlay/widget.py` | paintEvent 诊断、QColor 整数构造器、animate_show 调用 |
| `src/overlay/toolbar.py` | 毛玻璃 QSS、入场动画、按钮交互、GC 修复 |
| `src/ui/settings_dialog.py` | QComboBox signal 修复、QApplication import |
