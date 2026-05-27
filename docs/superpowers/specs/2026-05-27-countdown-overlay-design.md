# 截图延迟倒计时功能 - 设计文档

**日期**: 2026-05-27  
**版本**: 1.0  
**状态**: 待实现

---

## 1. 功能概述

当用户设置了截图延迟时间（1-10 秒）时，在触发截图快捷键后，显示一个全屏半透明倒计时覆盖层，让用户清楚知道何时开始截图，并可以在倒计时期间准备场景或取消操作。

**核心价值**：
- 解决延迟截图"不知道什么时候开始"的可用性问题
- 给用户足够时间准备截图场景（切换窗口、调整界面等）
- 提供清晰的视觉反馈和取消机制

---

## 2. 架构设计

### 2.1 新增组件

**CountdownOverlay** - 全屏倒计时覆盖层窗口
- 继承自 `QWidget`
- 无边框全屏窗口，置顶显示
- 半透明黑色背景，中央显示倒计时数字
- 每秒更新倒计时，支持 ESC 取消

### 2.2 修改组件

**SnipasteApp.start_capture()**
- 检测到 `capture_delay > 0` 时，创建并显示 CountdownOverlay
- 连接倒计时结束信号到 `_do_capture()`
- 连接取消信号到 `_on_countdown_cancelled()`

**SnipasteApp._do_capture()**
- 倒计时结束后调用（无需修改内部逻辑）

### 2.3 组件交互流程

```
用户触发截图（快捷键/托盘）
        ↓
SnipasteApp.start_capture()
        ↓
    检查 capture_delay
        ↓
  delay > 0 ?
   ↙        ↘
 是          否
  ↓          ↓
创建 CountdownOverlay    直接 _do_capture()
  ↓
显示倒计时覆盖层
  ↓
倒计时进行中...
  ↓
用户操作？
  ↙      ↘
等待      按 ESC
  ↓        ↓
倒计时结束   取消倒计时
  ↓        ↓
_do_capture()  清理，不截图
```

---

## 3. 用户交互流程

### 3.1 正常流程（等待倒计时完成）

1. 用户触发截图（快捷键 F12 / Cmd+Shift+X 或托盘菜单）
2. 应用检测到设置中的延迟时间 > 0 秒
3. 播放截图声音（如果启用）
4. 显示全屏半透明倒计时覆盖层
5. 倒计时从设置的秒数开始递减（例如：5...4...3...2...1）
6. 每秒更新屏幕中央的倒计时数字
7. 倒计时结束，覆盖层自动关闭
8. 执行 `_do_capture()`，进入截图编辑器

### 3.2 取消流程（用户按 ESC）

1. 倒计时进行中，用户按下 ESC 键
2. 倒计时覆盖层发送 `countdown_cancelled` 信号
3. 覆盖层关闭，不执行截图
4. 记录日志："用户取消延迟截图"

---

## 4. UI/UX 设计

### 4.1 视觉设计

**背景层：**
- 全屏覆盖，跨所有显示器（多显示器支持）
- 半透明黑色背景：`rgba(0, 0, 0, 0.6)`（60% 不透明度）
- 用户仍可透过背景看到屏幕内容，便于准备场景

**倒计时数字：**
- 位置：屏幕正中央（水平垂直居中）
- 字体：120px，粗体（QFont.Bold）
- 颜色：纯白色 `rgb(255, 255, 255)`
- 每秒切换数字时带淡入效果（200ms 过渡）

**提示文本：**
- 位置：倒计时数字下方 40px
- 内容：`"按 ESC 取消"` / `"Press ESC to cancel"`（国际化）
- 字体：24px，常规粗细
- 颜色：半透明白色 `rgba(255, 255, 255, 0.8)`

### 4.2 布局示意

```
┌──────────────────────────────────────┐
│ [半透明黑色背景 rgba(0,0,0,0.6)]     │
│                                      │
│                                      │
│              ┌─────┐                 │
│              │  3  │  ← 120px 白色   │
│              └─────┘                 │
│                                      │
│           按 ESC 取消  ← 24px 半透明  │
│                                      │
│                                      │
└──────────────────────────────────────┘
```

### 4.3 窗口属性

- **窗口类型**：无边框全屏窗口（`Qt.FramelessWindowHint`）
- **置顶**：`Qt.WindowStaysOnTopHint`
- **尺寸**：覆盖虚拟桌面（所有显示器）
- **鼠标穿透**：不启用（用户无法点击背景）

### 4.4 动画效果

**数字切换动画：**
- 新数字淡入（200ms）
- 使用 `QPropertyAnimation` 控制透明度
- 流畅自然，不过度花哨

---

## 5. 技术实现

### 5.1 新建文件：`src/ui/countdown_overlay.py`

```python
from PySide6.QtCore import Qt, QTimer, Signal, QPropertyAnimation
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
        
        # 设置窗口属性
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        
        # 全屏覆盖所有显示器
        screen = QApplication.primaryScreen()
        virtual_geometry = screen.virtualGeometry()
        self.setGeometry(virtual_geometry)
        
        # 启动定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_countdown)
        self._timer.start(1000)  # 每秒触发一次
        
        logger.info(f"倒计时覆盖层已创建，{seconds} 秒")
    
    def _update_countdown(self) -> None:
        """每秒更新倒计时"""
        self._seconds_left -= 1
        logger.debug(f"倒计时：{self._seconds_left}")
        
        if self._seconds_left <= 0:
            self._timer.stop()
            self.countdown_finished.emit()
            self.close()
        else:
            self.update()  # 触发重绘
    
    def paintEvent(self, event) -> None:
        """绘制倒计时界面"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 半透明黑色背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 153))  # 60% opacity
        
        # 绘制倒计时数字
        font = QFont("Arial", 120, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect(), Qt.AlignCenter, str(self._seconds_left))
        
        # 绘制提示文本
        hint_font = QFont("Arial", 24)
        painter.setFont(hint_font)
        painter.setPen(QColor(255, 255, 255, 204))  # 80% opacity
        hint_rect = self.rect().adjusted(0, 80, 0, 0)  # 下移 80px
        painter.drawText(hint_rect, Qt.AlignHCenter | Qt.AlignTop, 
                        _("Press ESC to cancel"))
    
    def keyPressEvent(self, event) -> None:
        """处理键盘事件"""
        if event.key() == Qt.Key_Escape:
            logger.info("用户按 ESC 取消倒计时")
            self._timer.stop()
            self.countdown_cancelled.emit()
            self.close()
        else:
            super().keyPressEvent(event)
```

### 5.2 修改文件：`src/app.py`

**在 `SnipasteApp.__init__` 中添加成员变量：**

```python
self.countdown_overlay: CountdownOverlay | None = None
```

**修改 `start_capture` 方法：**

```python
def start_capture(self) -> None:
    logger.info("start_capture() 被调用")
    _mac_activate_app()
    
    # 清理现有覆盖层
    if self.overlay is not None:
        self.overlay.close()
        self.overlay.deleteLater()
        self.overlay = None
    
    # 播放截图声音（延迟前播放）
    if self.settings.capture_sound:
        self._play_capture_sound()
    
    # 检查延迟设置
    delay_seconds = self.settings.capture_delay
    if delay_seconds > 0:
        logger.info(f"截图延迟 {delay_seconds} 秒，显示倒计时")
        from .ui.countdown_overlay import CountdownOverlay
        
        self.countdown_overlay = CountdownOverlay(delay_seconds)
        self.countdown_overlay.countdown_finished.connect(self._do_capture)
        self.countdown_overlay.countdown_cancelled.connect(self._on_countdown_cancelled)
        self.countdown_overlay.show()
        return
    
    self._do_capture()
```

**新增方法：**

```python
def _on_countdown_cancelled(self) -> None:
    """倒计时被用户取消"""
    logger.info("延迟截图已取消")
    if self.countdown_overlay:
        self.countdown_overlay.close()
        self.countdown_overlay.deleteLater()
        self.countdown_overlay = None
```

### 5.3 国际化翻译

**新增翻译项：`src/resources/locales/zh_CN.json`**

```json
{
  "Press ESC to cancel": "按 ESC 取消"
}
```

**新增翻译项：`src/resources/locales/zh_TW.json`**

```json
{
  "Press ESC to cancel": "按 ESC 取消"
}
```

---

## 6. 边界情况处理

### 6.1 多显示器支持

- **问题**：倒计时应该显示在哪个屏幕？
- **解决方案**：覆盖所有显示器的虚拟桌面，倒计时数字显示在主屏幕中央
- **实现**：使用 `QScreen.virtualGeometry()` 获取跨屏幕的总尺寸

### 6.2 重复触发快捷键

- **问题**：倒计时进行中，用户再次按截图快捷键
- **解决方案**：忽略重复触发，已有倒计时继续进行
- **实现**：在 `start_capture` 开头检查 `self.countdown_overlay is not None`，如果存在则直接返回

### 6.3 倒计时期间更改设置

- **问题**：倒计时进行中，用户打开设置修改延迟时间
- **解决方案**：不影响当前倒计时，新设置在下次截图时生效
- **实现**：倒计时创建时已固定秒数，不受后续设置变更影响

### 6.4 应用退出

- **问题**：倒计时进行中，用户退出应用
- **解决方案**：正常清理倒计时窗口，不执行截图
- **实现**：在 `cleanup()` 方法中检查并关闭 `countdown_overlay`

### 6.5 延迟时间为 0

- **问题**：设置中延迟时间为 0（或禁用）
- **解决方案**：跳过倒计时，直接执行截图
- **实现**：已在现有代码中处理：`if delay_seconds > 0`

---

## 7. 测试计划

### 7.1 功能测试

- [ ] 延迟 3 秒截图，倒计时显示正确
- [ ] 倒计时结束后自动进入截图编辑器
- [ ] 倒计时期间按 ESC 取消，不执行截图
- [ ] 多显示器环境下倒计时覆盖所有屏幕
- [ ] 倒计时数字切换流畅
- [ ] 延迟时间为 0 时，不显示倒计时，直接截图

### 7.2 边界测试

- [ ] 延迟最大值（10 秒）倒计时正常
- [ ] 延迟最小值（1 秒）倒计时正常
- [ ] 倒计时期间重复按快捷键，忽略重复触发
- [ ] 倒计时期间退出应用，正常清理资源
- [ ] 倒计时期间修改延迟设置，不影响当前倒计时

### 7.3 国际化测试

- [ ] 简体中文："按 ESC 取消"
- [ ] 繁体中文："按 ESC 取消"
- [ ] 英文："Press ESC to cancel"

### 7.4 平台测试

- [ ] Windows 系统倒计时显示正常
- [ ] macOS 系统倒计时显示正常
- [ ] Linux 系统倒计时显示正常（如有测试环境）

---

## 8. 后续优化方向

以下功能不在当前版本实现，留待后续优化：

1. **倒计时声音提示**：每秒"滴"一声，最后一秒"滴滴"提示
2. **倒计时动画增强**：数字缩放、渐变色等视觉效果
3. **倒计时可调速**：快进、暂停功能（低优先级）
4. **倒计时位置自定义**：让用户选择倒计时显示位置（中央/角落）

---

## 9. 实施计划

**预计工作量**：2-3 小时

**步骤**：
1. 创建 `countdown_overlay.py` 文件，实现 CountdownOverlay 类
2. 修改 `app.py`，集成倒计时逻辑
3. 添加国际化翻译（中英文）
4. 测试倒计时功能和 ESC 取消
5. 测试多显示器环境
6. 提交代码

---

## 10. 风险与依赖

**技术风险**：
- **低风险** - 功能独立，不影响现有截图流程

**依赖**：
- PySide6 的 QWidget、QTimer、QPainter
- 现有的国际化系统（i18n）
- 现有的日志系统（logger）

**兼容性**：
- 与现有截图流程完全兼容
- 不影响延迟时间为 0 的用户体验

---

**设计完成日期**：2026-05-27  
**设计者**：Claude Sonnet 4  
**审核者**：待审核
