# Pin 窗口功能增强设计

**创建日期**: 2026-05-29  
**目标**: 将 Pin 窗口功能对齐 Snipaste，提升视觉效果和交互体验

---

## 📋 概述

当前 Pin 窗口已有基础功能（阴影、缩放、调整大小、右键菜单、缩略图），但与 Snipaste 相比还有以下差距：
- 缺少 Hover 操作按钮（Snipaste 的标志性功能）
- 阴影和边框样式固定，不够精致
- 缺少双击快速操作
- 视觉过渡效果不够流畅

---

## 🎯 改进优先级

### 阶段 1：核心交互增强（高优先级）⭐⭐⭐

#### 1.1 Hover 操作按钮

**效果**：鼠标悬停在 Pin 窗口上时，右上角显示半透明操作按钮

**按钮列表**（从右到左）：
1. **关闭按钮** (×)
   - 功能：关闭 Pin 窗口
   - 图标：× (Unicode: ×)
   - 快捷键：无（鼠标操作）

2. **复制按钮** (📋)
   - 功能：复制图片到剪贴板
   - 图标：📋 (Unicode: \U0001F4CB) 或简单矩形图标
   - 快捷键：无

3. **保存按钮** (💾)
   - 功能：另存为文件
   - 图标：💾 (Unicode: \U0001F4BE) 或向下箭头
   - 快捷键：无

4. **缩略图按钮** (🔽)
   - 功能：切换缩略图模式
   - 图标：🔽 (Unicode: \U0001F53D) 或向下双箭头
   - 快捷键：无

**视觉设计**：
```
按钮尺寸: 28×28px
圆角: 6px
背景色: rgba(255, 255, 255, 0.85)
边框: 1px solid rgba(0, 0, 0, 0.1)
图标大小: 14×14px
图标颜色: #333333

Hover 状态:
背景色: rgba(255, 255, 255, 0.95)
阴影: 0 2px 4px rgba(0,0,0,0.15)

按钮间距: 4px
距离右边缘: 8px
距离顶边缘: 8px

动画:
- 淡入: 150ms ease-out (窗口 hover 时)
- 淡出: 200ms ease-in (离开 0.5s 后)
- 按钮 hover: 背景色过渡 100ms
```

**实现要点**：
```python
class HoverButton(QPushButton):
    """Hover 按钮组件"""
    def __init__(self, icon_text: str, tooltip: str, parent=None):
        super().__init__(icon_text, parent)
        self.setFixedSize(28, 28)
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        
        self.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 6px;
                color: #333;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.95);
            }
            QPushButton:pressed {
                background: rgba(240, 240, 240, 0.95);
            }
        """)

class PinWindow(QWidget):
    def __init__(self, ...):
        # 创建按钮容器
        self._hover_buttons = QWidget(self)
        self._hover_buttons.setVisible(False)
        
        # 创建按钮
        self._close_btn = HoverButton("×", _("Close"), self._hover_buttons)
        self._copy_btn = HoverButton("📋", _("Copy"), self._hover_buttons)
        self._save_btn = HoverButton("💾", _("Save As"), self._hover_buttons)
        self._thumb_btn = HoverButton("🔽", _("Thumbnail"), self._hover_buttons)
        
        # 布局
        layout = QHBoxLayout(self._hover_buttons)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._thumb_btn)
        layout.addWidget(self._save_btn)
        layout.addWidget(self._copy_btn)
        layout.addWidget(self._close_btn)
        
        # 信号连接
        self._close_btn.clicked.connect(self.close)
        self._copy_btn.clicked.connect(self._copy_to_clipboard)
        self._save_btn.clicked.connect(self._save_as)
        self._thumb_btn.clicked.connect(self._toggle_thumbnail)
        
        # 淡入淡出定时器
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out_buttons)
    
    def enterEvent(self, event):
        """鼠标进入"""
        self._hide_timer.stop()
        self._fade_in_buttons()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开 - 延迟隐藏"""
        self._hide_timer.start(500)
        super().leaveEvent(event)
    
    def _fade_in_buttons(self):
        """淡入按钮"""
        self._hover_buttons.setVisible(True)
        # TODO: 添加透明度动画
    
    def _fade_out_buttons(self):
        """淡出按钮"""
        # TODO: 添加透明度动画后隐藏
        self._hover_buttons.setVisible(False)
    
    def resizeEvent(self, event):
        """调整按钮容器位置"""
        super().resizeEvent(event)
        # 放置在右上角
        self._hover_buttons.adjustSize()
        x = self.width() - self._hover_buttons.width()
        self._hover_buttons.move(x, 0)
```

#### 1.2 双击快速复制

**效果**：双击 Pin 窗口图片区域，快速复制图片到剪贴板并显示 Toast 提示

**实现**：
```python
def mouseDoubleClickEvent(self, event):
    """双击复制到剪贴板"""
    if event.button() == Qt.LeftButton:
        # 检查是否点击在图片区域（非边框区域）
        if self._is_in_content_area(event.pos()):
            self._copy_to_clipboard()
            # 显示 Toast 提示
            from src.ui.toast import ToastManager
            ToastManager.show(
                _("Copied to clipboard"),
                "✓",
                "success",
                duration=1500,
                parent=self
            )
    super().mouseDoubleClickEvent(event)

def _is_in_content_area(self, pos: QPoint) -> bool:
    """判断是否在内容区域（排除边框调整区域）"""
    margin = 8  # 边框调整区域的宽度
    content_rect = self.rect().adjusted(margin, margin, -margin, -margin)
    return content_rect.contains(pos)
```

---

### 阶段 2：视觉美化（中优先级）⭐⭐

#### 2.1 边框和阴影优化

**当前问题**：
- 阴影固定为蓝色（`rgb(40, 120, 255)`），不够通用
- 没有细边框，视觉不够精致
- 阴影大小固定（4px），不可配置

**改进方案**：

**边框样式**：
```
宽度: 1px
颜色: rgba(0, 0, 0, 0.15)
位置: 内边框（避免影响尺寸计算）
```

**阴影默认值**：
```
颜色: rgba(0, 0, 0, 0.25) (中性灰，而非蓝色)
模糊半径: 6px (从 4px 增加)
偏移: 0, 2px (Y 轴向下偏移)
```

**可配置选项**（设置界面）：
```python
# src/core/settings.py - 添加配置项
pin_window_shadow_color: str = "rgba(0, 0, 0, 0.25)"
pin_window_shadow_blur: int = 6
pin_window_border_visible: bool = True
pin_window_border_color: str = "rgba(0, 0, 0, 0.15)"
```

**实现**：
```python
def paintEvent(self, event):
    """绘制边框"""
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)
    
    settings = get_settings()
    
    # 绘制边框（如果启用）
    if settings.pin_window_border_visible:
        border_color = QColor(settings.pin_window_border_color)
        pen = QPen(border_color, 1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        # 绘制内边框
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.drawRect(rect)
    
    super().paintEvent(event)

def _update_shadow(self):
    """更新阴影效果"""
    settings = get_settings()
    
    # 解析阴影颜色
    shadow_color = QColor(settings.pin_window_shadow_color)
    
    shadow = QGraphicsDropShadowEffect(self)
    shadow.setBlurRadius(settings.pin_window_shadow_blur)
    shadow.setColor(shadow_color)
    shadow.setOffset(0, 2)
    
    self.setGraphicsEffect(shadow)
```

#### 2.2 缩略图模式视觉优化

**当前状态**：缩略图模式只是简单缩小到 64×64，视觉效果一般

**改进方案**：

**缩略图样式**：
```
尺寸: 64×64px (保持)
圆角: 8px (从 0 增加)
阴影: 更明显 (blur 12px, offset 0,4px, rgba(0,0,0,0.3))
边框: 2px solid rgba(255,255,255,0.9) (白色外框，突出显示)
过渡动画: 200ms ease-in-out (尺寸、圆角、阴影同时过渡)
```

**实现**：
```python
def _toggle_thumbnail(self):
    """切换缩略图模式（带动画）"""
    if self._thumbnail_mode:
        # 恢复原始大小
        self._restore_from_thumbnail()
    else:
        # 缩小为缩略图
        self._shrink_to_thumbnail()

def _shrink_to_thumbnail(self):
    """缩小为缩略图（带动画）"""
    self._thumbnail_mode = True
    self._original_size = self.size()
    self._original_pos = self.pos()
    
    # 创建尺寸动画
    self._size_anim = QPropertyAnimation(self, b"size")
    self._size_anim.setDuration(200)
    self._size_anim.setStartValue(self.size())
    self._size_anim.setEndValue(QSize(64, 64))
    self._size_anim.setEasingCurve(QEasingCurve.InOutQuad)
    
    # 动画结束后更新样式
    self._size_anim.finished.connect(self._apply_thumbnail_style)
    self._size_anim.start()

def _apply_thumbnail_style(self):
    """应用缩略图样式"""
    # 更大的圆角
    self.setStyleSheet("""
        PinWindow {
            border-radius: 8px;
            border: 2px solid rgba(255, 255, 255, 0.9);
        }
    """)
    
    # 更明显的阴影
    shadow = QGraphicsDropShadowEffect(self)
    shadow.setBlurRadius(12)
    shadow.setColor(QColor(0, 0, 0, 76))  # rgba(0,0,0,0.3)
    shadow.setOffset(0, 4)
    self.setGraphicsEffect(shadow)

def _restore_from_thumbnail(self):
    """从缩略图恢复（带动画）"""
    self._thumbnail_mode = False
    
    # 创建尺寸动画
    self._size_anim = QPropertyAnimation(self, b"size")
    self._size_anim.setDuration(200)
    self._size_anim.setStartValue(self.size())
    self._size_anim.setEndValue(self._original_size)
    self._size_anim.setEasingCurve(QEasingCurve.InOutQuad)
    
    # 动画结束后恢复样式
    self._size_anim.finished.connect(self._restore_normal_style)
    self._size_anim.start()

def _restore_normal_style(self):
    """恢复正常样式"""
    self.setStyleSheet("")  # 清除缩略图样式
    self._update_shadow()   # 恢复正常阴影
```

---

### 阶段 3：高级功能（低优先级）⭐

#### 3.1 窗口吸附

**效果**：拖动 Pin 窗口接近屏幕边缘时，自动吸附对齐

**吸附规则**：
- 距离边缘 < 15px 时触发吸附
- 吸附后距离边缘 8px（留出空隙）
- 支持四个边缘：上、下、左、右
- 吸附时显示视觉反馈（边缘高亮）

**实现**（后续）：
```python
def mouseMoveEvent(self, event):
    """拖动时检测吸附"""
    if self._dragging:
        screen = QApplication.primaryScreen().geometry()
        global_pos = event.globalPosition().toPoint()
        
        # 计算新位置
        new_pos = global_pos - self._drag_offset
        
        # 吸附检测
        snap_threshold = 15
        snap_margin = 8
        
        # 左边缘
        if abs(new_pos.x()) < snap_threshold:
            new_pos.setX(snap_margin)
        
        # 右边缘
        if abs(new_pos.x() + self.width() - screen.width()) < snap_threshold:
            new_pos.setX(screen.width() - self.width() - snap_margin)
        
        # 上边缘
        if abs(new_pos.y()) < snap_threshold:
            new_pos.setY(snap_margin)
        
        # 下边缘
        if abs(new_pos.y() + self.height() - screen.height()) < snap_threshold:
            new_pos.setY(screen.height() - self.height() - snap_margin)
        
        self.move(new_pos)
    
    super().mouseMoveEvent(event)
```

#### 3.2 窗口管理器

**功能**：显示所有 Pin 窗口列表，支持批量操作

**界面**（后续设计）：
- 显示所有已固定窗口的缩略图列表
- 支持点击切换到对应窗口
- 批量关闭/隐藏操作
- 窗口分组功能

---

## 📊 实施计划

### 优先级排序

| 阶段 | 功能 | 工作量 | 优先级 | 依赖 |
|------|------|--------|--------|------|
| 1.1 | Hover 操作按钮 | 0.5 天 | ⭐⭐⭐ | 无 |
| 1.2 | 双击快速复制 | 0.5 天 | ⭐⭐⭐ | 无 |
| 2.1 | 边框和阴影优化 | 0.5 天 | ⭐⭐ | 无 |
| 2.2 | 缩略图模式优化 | 0.5 天 | ⭐⭐ | 无 |
| 3.1 | 窗口吸附 | 0.5 天 | ⭐ | 无 |
| 3.2 | 窗口管理器 | 1-2 天 | ⭐ | 所有窗口需要注册 |

**总计**: 阶段 1+2 约 2 天，完整实施约 3-4 天

---

## 🎨 视觉对比

### 当前效果
```
┌─────────────────────┐
│                     │ ← 无边框
│    [图片内容]       │ ← 固定蓝色阴影 4px
│                     │ ← 无 Hover 按钮
└─────────────────────┘
```

### 改进后效果
```
┌─────────────────────┐ [×][📋][💾][🔽] ← Hover 按钮
│ ─────────────────── │ ← 1px 细边框
│ │   [图片内容]    │ │ ← 灰色阴影 6px
│ ─────────────────── │ ← 双击复制
└─────────────────────┘
```

---

## 🔧 技术要点

### 需要修改的文件
- `src/ui/pin_window.py` - 主要逻辑
- `src/core/settings.py` - 添加配置项
- `src/ui/settings_dialog.py` - 设置界面（阴影配置）
- `src/resources/locales/*.json` - 翻译文件

### 测试要点
- [ ] Hover 按钮显示/隐藏流畅
- [ ] 双击复制功能正常
- [ ] 边框和阴影样式正确
- [ ] 缩略图模式动画流畅
- [ ] 设置项持久化正常

---

## 📝 用户反馈

**预期效果**：
- 更接近 Snipaste 的视觉和交互体验
- 快速操作更便捷（Hover 按钮 + 双击）
- 视觉更精致（边框 + 优化的阴影）
- 缩略图模式更美观

---

**最后更新**: 2026-05-29  
**状态**: 设计完成，待实施
