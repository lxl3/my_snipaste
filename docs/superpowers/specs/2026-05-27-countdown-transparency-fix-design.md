# 倒计时覆盖层透明度优化 - 设计文档

**日期**: 2026-05-27  
**版本**: 1.0  
**状态**: 已批准

---

## 1. 功能概述

优化截图延迟倒计时覆盖层的视觉效果，去除半透明黑色背景，改用描边技术确保倒计时数字在任何背景下都清晰可读，同时让用户能够完全看清屏幕内容。

**核心价值**：
- 完全消除背景遮挡，用户可以清楚看到屏幕内容准备截图场景
- 倒计时数字在任何背景颜色/图案下都保持清晰可读
- 视觉干扰最小化，提升用户体验

**问题背景**：
当前实现使用 10% 不透明度黑色背景（`QColor(0, 0, 0, 26)`），虽然已经很透明，但仍然影响用户查看背景内容。用户反馈"根本看不到后面的内容"，需要进一步优化。

---

## 2. 解决方案

### 2.1 核心方案

**采用描边（stroke）技术，类似视频字幕的实现方式：**

- **完全移除**全屏黑色半透明背景
- **使用 8 方向描边**确保文字在任何背景下清晰可读
- **技术原理**：在文字周围的 8 个方向（上、下、左、右、左上、右上、左下、右下）绘制黑色文字形成描边效果，然后在中心绘制白色文字

### 2.2 视觉效果对比

**修改前：**
```
┌────────────────────────────────┐
│ [10% 黑色半透明背景覆盖全屏]   │
│                                │
│         3                       │  ← 白色数字 + 单向阴影
│    按 ESC 取消                  │  ← 半透明白色文字
│                                │
└────────────────────────────────┘
```

**修改后：**
```
┌────────────────────────────────┐
│ [完全透明，背景内容完全可见]   │
│                                │
│         ③                       │  ← 白色数字 + 8 方向黑色描边
│    Ⓔⓢⓒ 取消                     │  ← 白色文字 + 8 方向黑色描边
│                                │
└────────────────────────────────┘
```

---

## 3. 技术实现

### 3.1 修改文件

**文件**：`src/ui/countdown_overlay.py`

**修改范围**：`paintEvent` 方法（第 66-95 行）

### 3.2 实现细节

#### 步骤 1：删除背景绘制

移除第 72 行：
```python
# 删除这一行
painter.fillRect(self.rect(), QColor(0, 0, 0, 26))  # 10% opacity
```

#### 步骤 2：实现 8 方向描边函数

为了代码复用，创建一个辅助方法绘制带描边的文字：

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
    
    Args:
        painter: QPainter 对象
        rect: 绘制区域
        flags: 对齐方式
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

#### 步骤 3：重写 paintEvent 方法

完整的 `paintEvent` 方法实现：

```python
def paintEvent(self, event) -> None:
    """绘制倒计时界面"""
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 不再绘制背景，完全透明
    
    # 绘制倒计时数字（带描边效果）
    font = QFont("Arial", 120, QFont.Bold)
    painter.setFont(font)
    
    self._draw_text_with_outline(
        painter,
        self.rect(),
        Qt.AlignCenter,
        str(self._seconds_left),
        QColor(255, 255, 255),      # 白色文字
        QColor(0, 0, 0, 200),       # 半透明黑色描边
        outline_width=3             # 3px 描边
    )
    
    # 绘制提示文本 "按 ESC 取消"（带描边效果）
    hint_font = QFont("Arial", 24)
    painter.setFont(hint_font)
    
    # 提示文本位于倒计时数字下方 40px
    hint_rect = self.rect().adjusted(0, 80, 0, 0)
    
    self._draw_text_with_outline(
        painter,
        hint_rect,
        Qt.AlignHCenter | Qt.AlignTop,
        _("Press ESC to cancel"),
        QColor(255, 255, 255, 230),  # 略微透明的白色文字
        QColor(0, 0, 0, 180),        # 半透明黑色描边
        outline_width=2              # 2px 描边
    )
```

### 3.3 参数调优

**描边宽度建议：**
- **倒计时数字**：3px（大号文字需要粗一点的描边）
- **提示文字**：2px（小号文字描边不宜过粗）

**颜色建议：**
- **文字颜色**：纯白色 `QColor(255, 255, 255)` 或略微透明 `QColor(255, 255, 255, 230)`
- **描边颜色**：半透明黑色 `QColor(0, 0, 0, 200)` 确保对比度，同时不过于生硬

这些参数可以根据实际测试效果微调。

---

## 4. 架构设计

### 4.1 改动范围

**最小化改动原则**：
- 只修改 `countdown_overlay.py` 文件
- 不影响其他组件
- 不改变信号机制和交互流程

### 4.2 组件关系

```
SnipasteApp
    ↓
    创建 CountdownOverlay
    ↓
CountdownOverlay.paintEvent()
    ↓
_draw_text_with_outline()  ← 新增辅助方法
    ↓
绘制带描边的文字（无背景）
```

---

## 5. 测试计划

### 5.1 功能测试

- [ ] 倒计时数字在**白色背景**下清晰可读
- [ ] 倒计时数字在**黑色背景**下清晰可读
- [ ] 倒计时数字在**彩色图片背景**下清晰可读
- [ ] 倒计时数字在**文字密集区域**下清晰可读
- [ ] 提示文字 "按 ESC 取消" 在各种背景下都清晰可读
- [ ] 背景内容完全可见，无任何遮挡
- [ ] 倒计时更新流畅，无闪烁

### 5.2 性能测试

- [ ] 绘制性能无明显下降（8 方向描边会增加绘制次数）
- [ ] 倒计时每秒更新流畅，CPU 占用正常
- [ ] 多显示器环境下性能正常

### 5.3 边界测试

- [ ] 多显示器环境，所有屏幕上文字都清晰
- [ ] 高 DPI 显示器（4K、Retina）上描边效果正常
- [ ] 倒计时从 10 秒到 1 秒，所有数字都清晰

### 5.4 回归测试

- [ ] ESC 取消功能正常
- [ ] 倒计时结束后正常进入截图编辑器
- [ ] 国际化翻译正常显示
- [ ] 不影响延迟为 0 时的直接截图

---

## 6. 风险与权衡

### 6.1 潜在风险

**风险 1：绘制性能**
- **问题**：8 方向描边意味着每个文字绘制 9 次（8 个描边 + 1 个中心）
- **评估**：低风险 - 只绘制 2 个文字（倒计时数字 + 提示），QPainter 性能足够
- **缓解**：如有性能问题，可减少描边方向（4 方向）或使用 QPainterPath

**风险 2：某些背景下对比度不足**
- **问题**：极端背景色（如中灰色）可能与白字黑边都接近
- **评估**：低风险 - 黑白对比是最大对比度，实际测试中很少见问题
- **缓解**：可调整描边颜色不透明度或增加描边宽度

### 6.2 设计权衡

**为什么选择 8 方向描边而不是 4 方向？**
- 4 方向（上下左右）在对角线方向可能有空隙
- 8 方向形成完整的环形描边，视觉效果更好
- 性能开销可接受（只有 2 段文字）

**为什么不使用 QPainterPath.strokePath？**
- QPainterPath 更复杂，对于简单场景过度设计
- 多次绘制文字的方式更直观，易于理解和维护
- 如果性能成为问题，可以后续优化为 QPainterPath

---

## 7. 后续优化方向

以下功能不在当前版本实现，留待后续优化：

1. **自适应描边宽度**：根据屏幕 DPI 动态调整描边宽度
2. **描边模糊效果**：使用 QGraphicsBlurEffect 实现更柔和的描边
3. **用户可配置**：允许用户在设置中选择"有背景"或"无背景"模式
4. **渐变描边**：使用渐变色描边实现更炫酷的视觉效果

---

## 8. 实施计划

**预计工作量**：30-45 分钟

**步骤**：
1. 在 `countdown_overlay.py` 中添加 `_draw_text_with_outline` 辅助方法（10 分钟）
2. 重写 `paintEvent` 方法，移除背景绘制，应用描边（15 分钟）
3. 测试不同背景下的显示效果，微调参数（15 分钟）
4. 提交代码（5 分钟）

---

## 9. 验收标准

**必须满足：**
✅ 倒计时覆盖层完全透明，背景内容完全可见  
✅ 倒计时数字在任何背景下都清晰可读  
✅ 提示文字 "按 ESC 取消" 清晰可读  
✅ 绘制性能流畅，无卡顿  
✅ 不影响现有功能（ESC 取消、倒计时结束触发截图）

**可选优化：**
⭐ 在 4K/Retina 高 DPI 屏幕上描边效果完美  
⭐ CPU 占用与原实现相当或更低

---

**设计完成日期**：2026-05-27  
**设计者**：Claude Sonnet 4  
**审核者**：用户已批准
