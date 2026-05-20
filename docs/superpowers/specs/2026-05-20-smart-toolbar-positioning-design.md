# 智能工具栏定位设计

**日期：** 2026-05-20  
**状态：** 已批准  
**作者：** Claude Sonnet 4

## 概述

实现类似 Snipaste 的智能工具栏定位：截图较小时工具栏显示在外部（下方），避免遮挡内容；截图较大时工具栏浮动在内部，方便操作。

## 背景和问题

### 当前实现

工具栏固定浮动在编辑器左上角 (10, 10) 位置，可拖动调整。

### 存在的问题

1. **小截图遮挡严重** — 200×150 的截图，800px 宽的工具栏几乎完全遮挡内容
2. **工具栏可能超出窗口** — 窗口缩小时工具栏可能显示不全
3. **用户体验不佳** — 需要手动拖动工具栏才能看清内容

### 用户需求

参考 Snipaste 的效果，实现自适应的工具栏定位。

## 设计目标

1. ✅ 小截图时工具栏不遮挡内容
2. ✅ 大截图时保持浮动工具栏的便捷性
3. ✅ 自动判断，无需用户干预
4. ✅ 保留拖动功能（浮动模式）
5. ✅ 适配不同 DPI 和屏幕尺寸

## 方案选择

### 对比的方案

**方案 1：固定阈值判断**
- 截图 < 400×300px → 外置
- 简单但不够灵活

**方案 2：相对尺寸自适应** ⭐ 选中
- 判断工具栏与截图的相对大小
- 更智能，适应性强

**方案 3：用户可选模式**
- 提供自动/浮动/外置三种模式
- 过度复杂

### 选择理由

方案 2 最接近 Snipaste 体验，无需用户配置，真正智能。

## 详细设计

### 1. 判断逻辑

```python
def _should_toolbar_float(self) -> bool:
    """判断工具栏应该浮动还是外置"""
    self.toolbar.adjustSize()
    
    toolbar_width = self.toolbar.width()
    toolbar_height = self.toolbar.height()
    
    # 获取截图逻辑尺寸（考虑 DPR）
    dpr = self.captured_pixmap.devicePixelRatio()
    logical_width = self.captured_pixmap.width() / dpr
    logical_height = self.captured_pixmap.height() / dpr
    
    # 计算占比
    width_ratio = toolbar_width / logical_width
    height_ratio = toolbar_height / logical_height
    
    # 判断：超过阈值则外置
    if width_ratio > 0.8 or height_ratio > 0.25:
        return False  # 外置
    return True  # 浮动
```

**阈值选择：**
- **宽度 0.8** — 工具栏占用超过 80% 宽度时太挤
- **高度 0.25** — 工具栏占用超过 25% 高度时影响内容查看

**DPR 处理：**
- 截图物理尺寸除以 DPR 得到逻辑尺寸
- 与工具栏逻辑尺寸在同一坐标系下比较

### 2. 布局调整

```python
def _position_toolbar(self):
    """智能定位工具栏"""
    self.toolbar.adjustSize()
    
    if self._should_toolbar_float():
        # 浮动模式：工具栏在视图内部
        self.toolbar.setParent(self.view)
        self.toolbar.move(10, 10)
        self.toolbar.show()
        self.toolbar.raise_()
    else:
        # 外置模式：工具栏在视图下方
        main_layout = self.layout()
        main_layout.addWidget(self.toolbar)
        
        # 扩展窗口高度
        toolbar_height = self.toolbar.height()
        current_height = self.height()
        self.resize(self.width(), current_height + toolbar_height + 8)
    
    # 通用设置
    self.toolbar.installEventFilter(self)
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(12)
    shadow.setOffset(2, 2)
    shadow.setColor(QColor(0, 0, 0, 120))
    self.toolbar.setGraphicsEffect(shadow)
```

**两种模式：**

| 模式 | 父组件 | 位置 | 窗口调整 |
|-----|--------|------|---------|
| 浮动 | `self.view` | (10, 10) | 无 |
| 外置 | 主布局 | 底部 | 高度 +toolbar_h +8 |

### 3. 窗口调整响应

```python
def resizeEvent(self, event):
    super().resizeEvent(event)
    
    # 浮动模式：限制工具栏边界
    if self.toolbar.parent() == self.view:
        self._constrain_toolbar_position()
    
    QTimer.singleShot(50, self.fit_in_view)

def _constrain_toolbar_position(self):
    """限制浮动工具栏在视图范围内"""
    if self.toolbar.parent() != self.view:
        return
    
    pos = self.toolbar.pos()
    max_x = self.view.width() - self.toolbar.width()
    max_y = self.view.height() - self.toolbar.height()
    
    new_x = max(0, min(pos.x(), max_x))
    new_y = max(0, min(pos.y(), max_y))
    
    if new_x != pos.x() or new_y != pos.y():
        self.toolbar.move(new_x, new_y)
```

**设计决策：**
- ❌ **不动态重新计算模式** — 初始化时决定，窗口调整不改变
- ✅ **边界限制** — 浮动工具栏不超出视图范围
- ✅ **保留现有逻辑** — `fit_in_view()` 延迟调用保持不变

### 4. 交互保留

**拖动功能：**
- 浮动模式：保留现有 `eventFilter` 拖动逻辑
- 外置模式：工具栏在布局中，不可拖动

```python
def eventFilter(self, obj, event):
    if obj is self.toolbar:
        # 只有浮动模式才能拖动
        if self.toolbar.parent() != self.view:
            return super().eventFilter(obj, event)
        
        # 现有拖动逻辑保持不变...
```

## 边界情况

### 1. 极小截图

**场景：** 50×50 的图标截图  
**处理：** 工具栏必定外置，窗口最小尺寸 `max(300, toolbar_width)` × `200 + toolbar_height`

### 2. 极窄/极宽截图

**场景：** 2000×100 的横幅截图  
**处理：** 高度判断触发外置（100 × 0.25 = 25px < 工具栏高度）

### 3. 工具栏尺寸变化

**场景：** 未来添加更多按钮  
**处理：** 初始化时计算，不动态响应。如需动态调整，暴露 `_position_toolbar()` 为公开方法重新调用。

## 测试场景

| 截图尺寸 | 工具栏尺寸 | DPR | 预期模式 | 验证点 |
|---------|-----------|-----|---------|--------|
| 200×150 | 800×60 | 1.5 | 外置 | 宽度比 > 0.8 |
| 800×600 | 800×60 | 1.0 | 浮动 | 恰好不超阈值 |
| 1920×1080 | 800×60 | 1.5 | 浮动 | 占比很小 |
| 400×200 | 800×60 | 1.0 | 外置 | 高度比 > 0.25 |
| 100×100 | 800×60 | 1.0 | 外置 | 极小截图 |

## 实现变更

### 修改的方法

1. **`EditorWindow.setup_ui()`**
   - 调用 `_position_toolbar()` 替代固定定位
   
2. **`EditorWindow.resizeEvent()`**
   - 添加 `_constrain_toolbar_position()` 调用

3. **`EditorWindow.eventFilter()`**
   - 添加浮动模式检查

### 新增的方法

1. **`_should_toolbar_float()`** — 判断逻辑
2. **`_position_toolbar()`** — 定位逻辑
3. **`_constrain_toolbar_position()`** — 边界限制

### 不变的部分

- ✅ 工具栏创建和样式
- ✅ 拖动事件处理逻辑（仅添加模式检查）
- ✅ 阴影效果
- ✅ 场景和视图设置

## 未来扩展

### 可能的优化

1. **动态调整** — 窗口调整时重新评估模式（需要记住用户手动拖动）
2. **用户偏好** — 允许用户固定选择某种模式
3. **更多定位选项** — 右侧、顶部等

### 暂不实现的原因

当前设计已满足核心需求，保持简单。等用户反馈再决定是否扩展。

## 总结

**核心价值：**
- 自动判断，无需配置
- 小截图不遮挡，大截图更便捷
- 完全兼容现有交互

**实现成本：**
- 低 — 3 个新方法，约 50 行代码
- 无破坏性变更

**用户体验提升：**
- 解决小截图显示问题
- 参考业界标准（Snipaste）
- 保持原有灵活性
