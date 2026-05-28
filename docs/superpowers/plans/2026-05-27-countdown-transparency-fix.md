# 倒计时透明度优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 去除倒计时覆盖层的半透明黑色背景，改用 8 方向描边技术确保文字在任何背景下都清晰可读

**Architecture:** 在 CountdownOverlay 类中添加 `_draw_text_with_outline` 辅助方法实现 8 方向描边效果，修改 `paintEvent` 方法移除背景绘制并应用描边到倒计时数字和提示文字

**Tech Stack:** PySide6 (QPainter, QColor, QFont), Qt Graphics System

---

## File Structure

**Modified files:**
- `src/ui/countdown_overlay.py:66-95` - 添加描边辅助方法，修改 paintEvent 移除背景并应用描边

**No new files created.**

---

## Task 1: 添加 8 方向描边辅助方法

**Files:**
- Modify: `src/ui/countdown_overlay.py`

- [ ] **Step 1: 在 CountdownOverlay 类中添加 _draw_text_with_outline 方法**

在 `closeEvent` 方法之后（第 115 行后）添加新方法：

```python
    def _draw_text_with_outline(
        self,
        painter: QPainter,
        rect,
        flags,
        text: str,
        text_color: QColor,
        outline_color: QColor,
        outline_width: int = 2
    ) -> None:
        """绘制带描边效果的文字
        
        使用 8 方向描边技术，确保文字在任何背景下都清晰可读（类似视频字幕）
        
        Args:
            painter: QPainter 对象
            rect: 绘制区域
            flags: 对齐方式（Qt.AlignCenter 等）
            text: 文字内容
            text_color: 文字颜色
            outline_color: 描边颜色
            outline_width: 描边宽度（像素）
        """
        # 8 个方向的偏移：上、下、左、右、左上、右上、左下、右下
        offsets = [
            (0, -outline_width),   # 上
            (0, outline_width),    # 下
            (-outline_width, 0),   # 左
            (outline_width, 0),    # 右
            (-outline_width, -outline_width),  # 左上
            (outline_width, -outline_width),   # 右上
            (-outline_width, outline_width),   # 左下
            (outline_width, outline_width),    # 右下
        ]
        
        # 先绘制 8 个方向的描边
        painter.setPen(outline_color)
        for dx, dy in offsets:
            outline_rect = rect.adjusted(dx, dy, dx, dy)
            painter.drawText(outline_rect, flags, text)
        
        # 最后绘制中心的文字
        painter.setPen(text_color)
        painter.drawText(rect, flags, text)
```

- [ ] **Step 2: 验证语法正确**

运行 Python 语法检查：

```bash
python -m py_compile src/ui/countdown_overlay.py
```

预期输出：无错误（命令成功执行）

---

## Task 2: 修改 paintEvent 移除背景并应用描边

**Files:**
- Modify: `src/ui/countdown_overlay.py:66-95`

- [ ] **Step 1: 备份当前 paintEvent 方法**

当前的 `paintEvent` 方法（第 66-95 行）需要完全重写。先在注释中记录旧的实现逻辑以便回滚。

- [ ] **Step 2: 重写 paintEvent 方法移除背景**

完全替换 `paintEvent` 方法（第 66-95 行）为以下实现：

```python
    def paintEvent(self, event) -> None:
        """绘制倒计时界面（无背景，使用描边技术）"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 不再绘制背景 - 完全透明，用户可以看清屏幕内容
        
        # 绘制倒计时数字（带 8 方向描边效果）
        font = QFont("Arial", 120, QFont.Bold)
        painter.setFont(font)
        
        self._draw_text_with_outline(
            painter,
            self.rect(),
            Qt.AlignCenter,
            str(self._seconds_left),
            QColor(255, 255, 255),      # 白色文字
            QColor(0, 0, 0, 200),       # 半透明黑色描边
            outline_width=3             # 3px 描边（大号文字）
        )
        
        # 绘制提示文本 "按 ESC 取消"（带描边效果）
        hint_font = QFont("Arial", 24)
        painter.setFont(hint_font)
        
        # 提示文本位于倒计时数字下方 80px
        hint_rect = self.rect().adjusted(0, 80, 0, 0)
        
        self._draw_text_with_outline(
            painter,
            hint_rect,
            Qt.AlignHCenter | Qt.AlignTop,
            _("Press ESC to cancel"),
            QColor(255, 255, 255, 230),  # 略微透明的白色文字
            QColor(0, 0, 0, 180),        # 半透明黑色描边
            outline_width=2              # 2px 描边（小号文字）
        )
```

- [ ] **Step 3: 验证语法正确**

```bash
python -m py_compile src/ui/countdown_overlay.py
```

预期输出：无错误

---

## Task 3: 测试不同背景下的显示效果

**Files:**
- Test: `src/ui/countdown_overlay.py`

- [ ] **Step 1: 启动应用并设置延迟截图**

```bash
# 启动应用
python -m src.main
```

在应用中：
1. 打开设置（托盘菜单 -> Preferences）
2. 找到 "Capture delay" 设置
3. 设置延迟为 3 秒
4. 保存设置

- [ ] **Step 2: 测试白色背景**

1. 打开一个白色背景窗口（如记事本、空白网页）
2. 最大化该窗口
3. 触发截图快捷键（默认 F12）
4. 观察倒计时数字是否清晰可见

**验收标准：**
- ✅ 背景完全透明，可以看清白色窗口
- ✅ 倒计时数字（白色 + 黑色描边）清晰可读
- ✅ 提示文字 "按 ESC 取消" 清晰可读

- [ ] **Step 3: 测试黑色背景**

1. 打开一个黑色背景窗口（如终端、黑色主题编辑器）
2. 最大化该窗口
3. 触发截图快捷键
4. 观察倒计时数字是否清晰可见

**验收标准：**
- ✅ 背景完全透明，可以看清黑色窗口
- ✅ 倒计时数字（白色 + 黑色描边）清晰可读

- [ ] **Step 4: 测试复杂彩色背景**

1. 打开一个包含复杂图片或彩色内容的窗口（如浏览器打开图片网站）
2. 触发截图快捷键
3. 观察倒计时数字是否清晰可见

**验收标准：**
- ✅ 背景完全透明，可以看清图片内容
- ✅ 倒计时数字清晰可读
- ✅ 描边效果形成完整的环形轮廓

- [ ] **Step 5: 测试 ESC 取消功能（回归测试）**

1. 设置延迟为 5 秒
2. 触发截图快捷键
3. 倒计时进行中按 ESC 键

**验收标准：**
- ✅ 倒计时窗口关闭
- ✅ 不进入截图编辑器
- ✅ 日志显示 "用户按 ESC 取消倒计时"

- [ ] **Step 6: 测试倒计时完成流程（回归测试）**

1. 设置延迟为 3 秒
2. 触发截图快捷键
3. 等待倒计时结束（3...2...1）

**验收标准：**
- ✅ 倒计时窗口自动关闭
- ✅ 正常进入截图编辑器
- ✅ 可以进行截图操作

- [ ] **Step 7: 测试延迟为 0 的情况（回归测试）**

1. 在设置中将延迟设为 0
2. 触发截图快捷键

**验收标准：**
- ✅ 不显示倒计时窗口
- ✅ 直接进入截图编辑器

---

## Task 4: 性能验证和微调

**Files:**
- Modify: `src/ui/countdown_overlay.py:66-95` (如需微调参数)

- [ ] **Step 1: 验证绘制性能**

1. 设置延迟为 10 秒
2. 触发截图快捷键
3. 使用任务管理器/活动监视器观察 CPU 占用
4. 观察倒计时数字更新是否流畅

**验收标准：**
- ✅ CPU 占用正常（< 5%）
- ✅ 倒计时每秒更新流畅，无卡顿
- ✅ 无闪烁现象

- [ ] **Step 2: 如需调整描边参数**

如果在测试中发现：
- 描边太粗/太细
- 对比度不够
- 某些背景下可读性不佳

可调整 `paintEvent` 中的参数：

**倒计时数字描边宽度**（当前 3px）：
```python
outline_width=3  # 可调整为 2-4
```

**倒计时数字描边颜色**（当前 `QColor(0, 0, 0, 200)`）：
```python
QColor(0, 0, 0, 200)  # alpha 值可调整为 180-220
```

**提示文字描边宽度**（当前 2px）：
```python
outline_width=2  # 可调整为 1-3
```

**提示文字描边颜色**（当前 `QColor(0, 0, 0, 180)`）：
```python
QColor(0, 0, 0, 180)  # alpha 值可调整为 160-200
```

- [ ] **Step 3: 重新测试微调后的效果**

如果修改了参数，重新执行 Task 3 的测试步骤验证效果。

---

## Task 5: 提交代码

**Files:**
- Commit: `src/ui/countdown_overlay.py`

- [ ] **Step 1: 检查修改内容**

```bash
git diff src/ui/countdown_overlay.py
```

预期看到：
- 新增 `_draw_text_with_outline` 方法
- `paintEvent` 方法移除了 `fillRect` 背景绘制
- `paintEvent` 方法使用 `_draw_text_with_outline` 绘制文字

- [ ] **Step 2: 运行快速回归测试**

1. 启动应用
2. 设置延迟 3 秒
3. 触发截图，观察倒计时
4. 按 ESC 取消
5. 再次触发截图，等待倒计时结束进入截图编辑器

确保所有基本功能正常。

- [ ] **Step 3: 添加并提交代码**

```bash
git add src/ui/countdown_overlay.py
git commit -m "$(cat <<'EOF'
fix: 移除倒计时背景并使用描边技术提升可读性

问题：
- 10% 黑色半透明背景仍然遮挡屏幕内容
- 用户无法完全看清背景准备截图场景

解决方案：
- 完全移除 fillRect 背景绘制
- 新增 _draw_text_with_outline 方法实现 8 方向描边
- 倒计时数字：3px 黑色描边 + 白色文字
- 提示文字：2px 黑色描边 + 白色文字

效果：
- 背景完全透明，用户可看清屏幕内容
- 描边技术确保文字在任何背景下清晰可读
- 类似视频字幕的视觉效果

测试：
- ✅ 白色背景下文字清晰
- ✅ 黑色背景下文字清晰
- ✅ 复杂彩色背景下文字清晰
- ✅ ESC 取消功能正常
- ✅ 倒计时完成进入截图正常
- ✅ 延迟为 0 时直接截图正常

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: 验证提交**

```bash
git log --oneline -1
git show HEAD --stat
```

预期看到：
- 提交信息包含详细的修改说明
- 只修改了 `src/ui/countdown_overlay.py` 一个文件

---

## Testing Checklist

### 功能测试
- [ ] 白色背景：倒计时数字清晰可读
- [ ] 黑色背景：倒计时数字清晰可读
- [ ] 彩色/复杂背景：倒计时数字清晰可读
- [ ] 背景内容完全可见，无遮挡
- [ ] 提示文字 "按 ESC 取消" 清晰可读

### 性能测试
- [ ] CPU 占用正常（< 5%）
- [ ] 倒计时更新流畅，无卡顿
- [ ] 无闪烁现象

### 回归测试
- [ ] ESC 取消：倒计时中止，不执行截图
- [ ] 倒计时结束：自动进入截图编辑器
- [ ] 延迟为 0：不显示倒计时，直接截图
- [ ] 国际化：中英文提示文字正常显示

### 边界测试
- [ ] 多显示器环境：倒计时在所有屏幕上都清晰
- [ ] 高 DPI 屏幕（4K/Retina）：描边效果正常
- [ ] 倒计时从 10 秒到 1 秒：所有数字都清晰

---

## Rollback Plan

如果新实现有问题，可以快速回滚：

```bash
# 回滚到上一个提交
git revert HEAD

# 或者重置（如果还没推送）
git reset --hard HEAD~1
```

原有的实现使用单向阴影 + 10% 黑色背景，虽然不够透明但至少可用。

---

## Future Enhancements

以下优化不在当前计划中，留待后续：

1. **自适应描边宽度**：根据屏幕 DPI 动态调整描边宽度
2. **QPainterPath 优化**：如果性能成为问题，可用 QPainterPath.strokePath 替代多次绘制
3. **用户可配置**：在设置中提供"有背景"或"无背景"选项
4. **渐变描边**：使用渐变色实现更炫酷的视觉效果

---

**Plan created**: 2026-05-27  
**Spec reference**: `docs/superpowers/specs/2026-05-27-countdown-transparency-fix-design.md`  
**Estimated time**: 30-45 minutes