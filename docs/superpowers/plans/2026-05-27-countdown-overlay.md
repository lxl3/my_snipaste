# 截图延迟倒计时覆盖层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现全屏倒计时覆盖层，在延迟截图时显示倒计时，支持 ESC 取消

**Architecture:** 创建独立的 CountdownOverlay 组件，通过信号机制与 SnipasteApp 通信。倒计时结束或取消时发送信号，由 app 决定后续操作（执行截图或清理）。

**Tech Stack:** PySide6 (QWidget, QTimer, QPainter), Qt Signals/Slots

---

## File Structure

**New files:**
- `src/ui/countdown_overlay.py` - 倒计时覆盖层组件，负责全屏显示、倒计时逻辑、UI 绘制、键盘事件

**Modified files:**
- `src/app.py` - 集成倒计时覆盖层，在 start_capture 中检测延迟设置
- `src/resources/locales/zh_CN.json` - 简体中文翻译
- `src/resources/locales/zh_TW.json` - 繁体中文翻译

---

## Task 1: 创建 CountdownOverlay 基础结构

**Files:**
- Create: `src/ui/countdown_overlay.py`

- [ ] **Step 1: 创建 CountdownOverlay 类框架**

创建文件 `src/ui/countdown_overlay.py`，定义基础类结构和信号：

```python
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import QWidget, QApplication

from ..core.i18n import _
from ..core.logger import setup_logger

logger = setup_logger("countdown_overlay")


class CountdownOverlay(QWidget):
    """全屏倒计时覆盖层"""
    
    countdown_finished = Signal()  # 倒计时结束
    countdown_cancelled = Signal()  # 用户取消
    
    def __init__(self, seconds: int):
        super().__init__()
        self._seconds_left = seconds
        self._timer: QTimer | None = None
        
        logger.info(f"CountdownOverlay 初始化，倒计时 {seconds} 秒")
```

- [ ] **Step 2: 配置窗口属性**

在 `__init__` 方法中添加窗口配置：

```python
    def __init__(self, seconds: int):
        super().__init__()
        self._seconds_left = seconds
        self._timer: QTimer | None = None
        
        # 设置窗口属性：无边框、置顶、工具窗口
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        
        # 设置为全屏覆盖所有显示器
        screen = QApplication.primaryScreen()
        if screen:
            virtual_geometry = screen.virtualGeometry()
            self.setGeometry(virtual_geometry)
        
        logger.info(f"CountdownOverlay 初始化，倒计时 {seconds} 秒")
```

- [ ] **Step 3: 验证窗口创建**

在 app.py 中临时测试窗口创建（稍后会移除）：

```python
# 在 app.py 的 start_capture 方法末尾临时添加
from .ui.countdown_overlay import CountdownOverlay
test_overlay = CountdownOverlay(3)
test_overlay.show()
```

运行应用，触发截图，应该看到一个空白全屏窗口。

- [ ] **Step 4: 移除测试代码**

移除 app.py 中添加的测试代码。

- [ ] **Step 5: 提交基础结构**

```bash
git add src/ui/countdown_overlay.py
git commit -m "feat: 添加 CountdownOverlay 基础结构

- 创建全屏倒计时覆盖层类
- 配置窗口属性：无边框、置顶、全屏
- 定义 countdown_finished 和 countdown_cancelled 信号

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 2: 实现倒计时逻辑

**Files:**
- Modify: `src/ui/countdown_overlay.py`

- [ ] **Step 1: 添加定时器初始化**

在 `__init__` 方法中初始化 QTimer：

```python
    def __init__(self, seconds: int):
        super().__init__()
        self._seconds_left = seconds
        self._timer: QTimer | None = None
        
        # 设置窗口属性
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        
        # 全屏覆盖
        screen = QApplication.primaryScreen()
        if screen:
            virtual_geometry = screen.virtualGeometry()
            self.setGeometry(virtual_geometry)
        
        # 初始化定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_countdown)
        self._timer.start(1000)  # 每秒触发一次
        
        logger.info(f"CountdownOverlay 初始化，倒计时 {seconds} 秒")
```

- [ ] **Step 2: 实现倒计时更新方法**

在类中添加 `_update_countdown` 方法：

```python
    def _update_countdown(self) -> None:
        """每秒更新倒计时"""
        self._seconds_left -= 1
        logger.debug(f"倒计时：{self._seconds_left} 秒")
        
        if self._seconds_left <= 0:
            # 倒计时结束
            logger.info("倒计时结束，发送 countdown_finished 信号")
            if self._timer:
                self._timer.stop()
            self.countdown_finished.emit()
            self.close()
        else:
            # 触发重绘以更新显示的数字
            self.update()
```

- [ ] **Step 3: 添加清理方法**

添加资源清理方法：

```python
    def closeEvent(self, event) -> None:
        """窗口关闭时清理资源"""
        if self._timer:
            self._timer.stop()
            self._timer = None
        logger.debug("CountdownOverlay 已关闭")
        super().closeEvent(event)
```

- [ ] **Step 4: 提交倒计时逻辑**

```bash
git add src/ui/countdown_overlay.py
git commit -m "feat: 实现倒计时逻辑

- 添加 QTimer 每秒更新倒计时
- 倒计时结束时发送 countdown_finished 信号
- 添加资源清理逻辑

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 3: 实现 UI 绘制

**Files:**
- Modify: `src/ui/countdown_overlay.py`

- [ ] **Step 1: 实现 paintEvent 方法**

添加 `paintEvent` 方法绘制倒计时界面：

```python
    def paintEvent(self, event) -> None:
        """绘制倒计时界面"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制半透明黑色背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 153))  # 60% opacity (255 * 0.6 = 153)
        
        # 绘制倒计时数字
        font = QFont("Arial", 120, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect(), Qt.AlignCenter, str(self._seconds_left))
        
        # 绘制提示文本 "按 ESC 取消"
        hint_font = QFont("Arial", 24)
        painter.setFont(hint_font)
        painter.setPen(QColor(255, 255, 255, 204))  # 80% opacity (255 * 0.8 = 204)
        
        # 提示文本位于倒计时数字下方 40px
        hint_rect = self.rect().adjusted(0, 80, 0, 0)
        painter.drawText(hint_rect, Qt.AlignHCenter | Qt.AlignTop, 
                        _("Press ESC to cancel"))
```

- [ ] **Step 2: 测试 UI 显示**

在 app.py 中临时测试 UI（稍后移除）：

```python
# 在 start_capture 方法中临时添加
from .ui.countdown_overlay import CountdownOverlay
test_overlay = CountdownOverlay(5)
test_overlay.show()
```

运行应用，触发截图，应该看到：
- 半透明黑色背景
- 屏幕中央白色大号数字（5, 4, 3, 2, 1）
- 数字下方提示文本

- [ ] **Step 3: 移除测试代码**

移除 app.py 中的测试代码。

- [ ] **Step 4: 提交 UI 绘制**

```bash
git add src/ui/countdown_overlay.py
git commit -m "feat: 实现倒计时 UI 绘制

- 绘制半透明黑色背景
- 绘制白色大号倒计时数字
- 绘制提示文本（需要国际化）

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 4: 实现键盘事件处理

**Files:**
- Modify: `src/ui/countdown_overlay.py`

- [ ] **Step 1: 实现 keyPressEvent 方法**

添加键盘事件处理，监听 ESC 键：

```python
    def keyPressEvent(self, event) -> None:
        """处理键盘事件"""
        if event.key() == Qt.Key_Escape:
            logger.info("用户按 ESC 取消倒计时")
            if self._timer:
                self._timer.stop()
            self.countdown_cancelled.emit()
            self.close()
        else:
            super().keyPressEvent(event)
```

- [ ] **Step 2: 测试 ESC 取消**

在 app.py 中临时测试 ESC 取消：

```python
# 在 start_capture 方法中
from .ui.countdown_overlay import CountdownOverlay
test_overlay = CountdownOverlay(10)
test_overlay.countdown_cancelled.connect(lambda: logger.info("倒计时已取消"))
test_overlay.show()
```

运行应用，触发截图，按 ESC 键，应该看到：
- 倒计时窗口关闭
- 日志输出："用户按 ESC 取消倒计时"

- [ ] **Step 3: 移除测试代码**

移除 app.py 中的测试代码。

- [ ] **Step 4: 提交键盘事件处理**

```bash
git add src/ui/countdown_overlay.py
git commit -m "feat: 实现 ESC 键取消倒计时

- 监听 ESC 键事件
- 按 ESC 时停止定时器并发送 countdown_cancelled 信号
- 关闭倒计时窗口

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 5: 集成到 SnipasteApp

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: 添加成员变量**

在 `SnipasteApp.__init__` 方法中添加 countdown_overlay 成员变量。

找到这一行（大约在第 69 行）：
```python
self.overlay: CaptureOverlay | None = None
```

在其后添加：
```python
self.countdown_overlay: CountdownOverlay | None = None
```

同时在文件顶部添加导入（在其他 ui 导入之后）：
```python
from .ui.countdown_overlay import CountdownOverlay
```

- [ ] **Step 2: 修改 start_capture 方法**

找到 `start_capture` 方法（大约在第 154 行），修改延迟截图逻辑。

将这段代码：
```python
    # Check capture delay setting
    delay_seconds = self.settings.capture_delay
    if delay_seconds > 0:
        logger.info(f"截图延迟 {delay_seconds} 秒")
        QTimer.singleShot(delay_seconds * 1000, self._do_capture)
        return
    
    self._do_capture()
```

替换为：
```python
    # Check capture delay setting
    delay_seconds = self.settings.capture_delay
    if delay_seconds > 0:
        logger.info(f"截图延迟 {delay_seconds} 秒，显示倒计时")
        self.countdown_overlay = CountdownOverlay(delay_seconds)
        self.countdown_overlay.countdown_finished.connect(self._do_capture)
        self.countdown_overlay.countdown_cancelled.connect(self._on_countdown_cancelled)
        self.countdown_overlay.show()
        return
    
    self._do_capture()
```

- [ ] **Step 3: 添加取消处理方法**

在 `start_capture` 方法之后添加新方法 `_on_countdown_cancelled`：

```python
    def _on_countdown_cancelled(self) -> None:
        """倒计时被用户取消"""
        logger.info("延迟截图已取消")
        if self.countdown_overlay:
            self.countdown_overlay.close()
            self.countdown_overlay.deleteLater()
            self.countdown_overlay = None
```

- [ ] **Step 4: 完善资源清理**

在 `cleanup` 方法中（大约在第 349 行）添加倒计时覆盖层的清理。

找到这段代码：
```python
    def cleanup(self) -> None:
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()
```

在其后添加：
```python
        if hasattr(self, 'countdown_overlay') and self.countdown_overlay:
            self.countdown_overlay.close()
            self.countdown_overlay = None
```

- [ ] **Step 5: 测试集成**

运行应用，测试以下场景：

1. **正常倒计时流程**：
   - 打开设置，设置截图延迟为 3 秒
   - 触发截图快捷键
   - 应该看到倒计时覆盖层显示 3...2...1
   - 倒计时结束后自动进入截图编辑器

2. **ESC 取消流程**：
   - 设置截图延迟为 5 秒
   - 触发截图快捷键
   - 倒计时进行中按 ESC
   - 倒计时窗口关闭，不进入截图

3. **延迟为 0**：
   - 设置延迟为 0
   - 触发截图
   - 不显示倒计时，直接进入截图

- [ ] **Step 6: 提交集成代码**

```bash
git add src/app.py
git commit -m "feat: 集成倒计时覆盖层到截图流程

- 在 start_capture 中检测延迟设置
- 延迟 > 0 时创建并显示 CountdownOverlay
- 连接倒计时结束信号到 _do_capture
- 连接取消信号到 _on_countdown_cancelled
- 在 cleanup 中清理倒计时资源

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 6: 添加国际化翻译

**Files:**
- Modify: `src/resources/locales/zh_CN.json`
- Modify: `src/resources/locales/zh_TW.json`

- [ ] **Step 1: 添加简体中文翻译**

编辑 `src/resources/locales/zh_CN.json`，在最后一个条目后添加（注意逗号）：

```json
  "Press ESC to cancel": "按 ESC 取消"
```

完整示例（注意前一行的逗号）：
```json
  "💡 Double-click or press Enter to save": "💡 双击或按 Enter 自动保存",
  "Press ESC to cancel": "按 ESC 取消"
}
```

- [ ] **Step 2: 添加繁体中文翻译**

编辑 `src/resources/locales/zh_TW.json`，在最后一个条目后添加（注意逗号）：

```json
  "Press ESC to cancel": "按 ESC 取消"
```

完整示例：
```json
  "💡 Double-click or press Enter to save": "💡 雙擊或按 Enter 自動儲存",
  "Press ESC to cancel": "按 ESC 取消"
}
```

- [ ] **Step 3: 测试国际化**

运行应用，在设置中切换语言：

1. **简体中文**：
   - 设置延迟截图
   - 触发截图
   - 倒计时窗口应显示："按 ESC 取消"

2. **繁体中文**：
   - 切换到繁体中文
   - 触发截图
   - 倒计时窗口应显示："按 ESC 取消"

3. **英文**：
   - 切换到英文
   - 触发截图
   - 倒计时窗口应显示："Press ESC to cancel"

- [ ] **Step 4: 提交翻译**

```bash
git add src/resources/locales/zh_CN.json src/resources/locales/zh_TW.json
git commit -m "feat: 添加倒计时覆盖层国际化翻译

- 简体中文：按 ESC 取消
- 繁体中文：按 ESC 取消
- 英文使用原文：Press ESC to cancel

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 7: 完整功能测试和文档更新

**Files:**
- Modify: `README.md` (optional)

- [ ] **Step 1: 完整功能测试**

测试所有场景：

**基础功能：**
- [ ] 延迟 1 秒截图，倒计时正常
- [ ] 延迟 5 秒截图，倒计时正常
- [ ] 延迟 10 秒截图，倒计时正常
- [ ] 延迟 0 秒（禁用），不显示倒计时
- [ ] 倒计时结束后正常进入截图编辑器
- [ ] 倒计时期间按 ESC 取消，不进入截图

**边界情况：**
- [ ] 倒计时进行中重复按截图快捷键（当前会创建新倒计时，可接受）
- [ ] 倒计时进行中退出应用，正常清理资源
- [ ] 多显示器环境，倒计时覆盖所有屏幕

**国际化：**
- [ ] 简体中文提示正确
- [ ] 繁体中文提示正确
- [ ] 英文提示正确

**平台测试：**
- [ ] Windows 系统正常工作
- [ ] macOS 系统正常工作（如有环境）

- [ ] **Step 2: 可选 - 更新 README**

如果希望在 README 中说明延迟截图功能，可以在"截图行为"部分添加说明：

```markdown
### 截图延迟

当设置了截图延迟（1-10 秒）时，触发截图后会显示全屏倒计时覆盖层：
- 屏幕中央显示倒计时数字（3...2...1）
- 倒计时期间可以按 ESC 取消
- 倒计时结束后自动进入截图编辑器
```

- [ ] **Step 3: 最终提交**

如果修改了 README：

```bash
git add README.md
git commit -m "docs: 更新 README 说明延迟截图倒计时功能

- 添加倒计时覆盖层功能说明
- 说明 ESC 取消机制

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

- [ ] **Step 4: 推送到远程仓库**

```bash
git push origin master
```

---

## Testing Checklist

### 功能测试
- [ ] 延迟 1 秒：倒计时显示正确，自动截图
- [ ] 延迟 3 秒：倒计时显示正确，自动截图
- [ ] 延迟 10 秒：倒计时显示正确，自动截图
- [ ] 延迟 0 秒：不显示倒计时，直接截图
- [ ] ESC 取消：倒计时中止，不执行截图
- [ ] 倒计时结束：自动关闭覆盖层，进入截图编辑器

### 边界测试
- [ ] 多显示器：倒计时覆盖所有屏幕
- [ ] 重复触发：倒计时进行中再次按快捷键的行为
- [ ] 应用退出：倒计时期间退出应用，资源正常清理

### 国际化测试
- [ ] 简体中文："按 ESC 取消"
- [ ] 繁体中文："按 ESC 取消"
- [ ] 英文："Press ESC to cancel"

### 平台测试
- [ ] Windows 系统倒计时显示正常
- [ ] macOS 系统倒计时显示正常
- [ ] Linux 系统倒计时显示正常（如有环境）

---

## Known Issues & Future Enhancements

### 当前已知问题
无

### 未来增强方向
1. **倒计时声音提示**：每秒"滴"一声，最后一秒"滴滴"
2. **倒计时动画**：数字缩放、渐变色效果
3. **重复触发处理**：倒计时进行中再次触发快捷键，是否重置倒计时？
4. **倒计时位置自定义**：允许用户选择倒计时显示位置

---

## Estimated Time

**Total**: 2-3 hours

- Task 1: 创建基础结构 - 20 分钟
- Task 2: 实现倒计时逻辑 - 20 分钟
- Task 3: 实现 UI 绘制 - 30 分钟
- Task 4: 实现键盘事件 - 15 分钟
- Task 5: 集成到 SnipasteApp - 30 分钟
- Task 6: 国际化翻译 - 15 分钟
- Task 7: 测试和文档 - 30 分钟

---

**Plan created**: 2026-05-27  
**Spec reference**: `docs/superpowers/specs/2026-05-27-countdown-overlay-design.md`
