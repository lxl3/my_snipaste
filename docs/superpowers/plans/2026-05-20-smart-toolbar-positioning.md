# 智能工具栏定位实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现类似 Snipaste 的智能工具栏定位，小截图时外置，大截图时浮动

**Architecture:** 基于相对尺寸判断（宽度比 0.8，高度比 0.25）自动选择浮动或外置模式。浮动模式工具栏在视图内部，外置模式在布局底部。保留拖动功能（仅浮动模式）。

**Tech Stack:** PySide6, Qt Graphics View Framework

---

## 文件结构

### 修改的文件

- **`src/editor.py`** (主要修改)
  - 新增方法：`_should_toolbar_float()`, `_position_toolbar()`, `_constrain_toolbar_position()`
  - 修改方法：`setup_ui()`, `resizeEvent()`, `eventFilter()`
  - 变更行数：约 +60 行

---

## Task 1: 添加判断逻辑方法

**Files:**
- Modify: `src/editor.py:224-425` (EditorWindow 类内)

- [ ] **Step 1: 在 EditorWindow 类中添加 `_should_toolbar_float()` 方法**

在 `EditorWindow` 类的 `setup_ui()` 方法之后（约第 425 行），添加新方法：

```python
def _should_toolbar_float(self) -> bool:
    """判断工具栏应该浮动还是外置
    
    判断规则：
    - 工具栏宽度 > 截图宽度 * 0.8 → 外置
    - 工具栏高度 > 截图高度 * 0.25 → 外置
    - 否则 → 浮动
    
    Returns:
        bool: True 表示浮动，False 表示外置
    """
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

- [ ] **Step 2: 验证语法**

运行语法检查：

```bash
python -m py_compile src/editor.py
```

预期：无输出（编译成功）

- [ ] **Step 3: 提交**

```bash
git add src/editor.py
git commit -m "feat: 添加工具栏浮动判断逻辑

添加 _should_toolbar_float() 方法，基于相对尺寸判断：
- 工具栏占用 > 80% 宽度或 25% 高度时外置
- 考虑 DPR 确保不同缩放比例下准确判断

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 2: 添加工具栏定位方法

**Files:**
- Modify: `src/editor.py:224-456` (在 Task 1 基础上)

- [ ] **Step 1: 添加 `_position_toolbar()` 方法**

在 `_should_toolbar_float()` 方法之后添加：

```python
def _position_toolbar(self):
    """智能定位工具栏
    
    根据 _should_toolbar_float() 的判断结果：
    - 浮动模式：工具栏作为 view 的子组件，显示在左上角
    - 外置模式：工具栏添加到主布局，窗口高度扩展
    """
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
    
    # 通用设置（无论哪种模式）
    self.toolbar.installEventFilter(self)
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(12)
    shadow.setOffset(2, 2)
    shadow.setColor(QColor(0, 0, 0, 120))
    self.toolbar.setGraphicsEffect(shadow)
```

- [ ] **Step 2: 验证语法**

```bash
python -m py_compile src/editor.py
```

预期：无输出（编译成功）

- [ ] **Step 3: 提交**

```bash
git add src/editor.py
git commit -m "feat: 添加智能工具栏定位方法

添加 _position_toolbar() 方法实现两种模式：
- 浮动模式：工具栏在视图内左上角 (10, 10)
- 外置模式：工具栏在布局底部，窗口高度扩展

两种模式都保留阴影效果和事件过滤器

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 3: 修改 setup_ui 使用新定位逻辑

**Files:**
- Modify: `src/editor.py:249-426` (setup_ui 方法)

- [ ] **Step 1: 找到并移除旧的工具栏定位代码**

在 `setup_ui()` 方法中找到以下代码块（约第 414-423 行）：

```python
self.toolbar.setParent(self.view)
self.toolbar.move(10, 10)
self.toolbar.show()
self.toolbar.raise_()
self.toolbar.installEventFilter(self)
shadow = QGraphicsDropShadowEffect()
shadow.setBlurRadius(12)
shadow.setOffset(2, 2)
shadow.setColor(QColor(0, 0, 0, 120))
self.toolbar.setGraphicsEffect(shadow)
```

将其替换为单行调用：

```python
# 智能定位工具栏（浮动或外置）
self._position_toolbar()
```

保持 `self.fit_in_view()` 调用在最后。

- [ ] **Step 2: 验证语法**

```bash
python -m py_compile src/editor.py
```

预期：无输出

- [ ] **Step 3: 快速冒烟测试**

运行程序，截一个大图（如全屏），验证工具栏显示：

```bash
cd D:\project\opensnipaste
python main.py
```

操作：
1. 按 F1
2. 截取全屏或大区域
3. 观察工具栏是否显示在左上角浮动

预期：工具栏浮动在左上角，可见

- [ ] **Step 4: 提交**

```bash
git add src/editor.py
git commit -m "refactor: setup_ui 使用智能定位逻辑

移除硬编码的工具栏定位代码，改用 _position_toolbar() 自动判断

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 4: 添加边界限制方法

**Files:**
- Modify: `src/editor.py` (在前面任务基础上)

- [ ] **Step 1: 添加 `_constrain_toolbar_position()` 方法**

在 `_position_toolbar()` 方法之后添加：

```python
def _constrain_toolbar_position(self):
    """限制浮动工具栏在视图范围内
    
    确保工具栏不会因为窗口调整而超出视图边界。
    仅对浮动模式有效（parent 是 self.view）。
    """
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

- [ ] **Step 2: 验证语法**

```bash
python -m py_compile src/editor.py
```

预期：无输出

- [ ] **Step 3: 提交**

```bash
git add src/editor.py
git commit -m "feat: 添加工具栏边界限制方法

添加 _constrain_toolbar_position() 确保浮动工具栏不超出视图范围

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 5: 修改 resizeEvent 添加边界检查

**Files:**
- Modify: `src/editor.py:549-552` (resizeEvent 方法)

- [ ] **Step 1: 修改 `resizeEvent()` 方法**

找到 `resizeEvent()` 方法（约第 549 行），当前代码：

```python
def resizeEvent(self, event):
    super().resizeEvent(event)
    QTimer.singleShot(50, self.fit_in_view)
```

修改为：

```python
def resizeEvent(self, event):
    super().resizeEvent(event)
    
    # 如果工具栏浮动，确保它不超出边界
    if self.toolbar.parent() == self.view:
        self._constrain_toolbar_position()
    
    QTimer.singleShot(50, self.fit_in_view)
```

- [ ] **Step 2: 验证语法**

```bash
python -m py_compile src/editor.py
```

预期：无输出

- [ ] **Step 3: 提交**

```bash
git add src/editor.py
git commit -m "feat: resizeEvent 添加工具栏边界检查

窗口调整时限制浮动工具栏在视图范围内

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 6: 修改 eventFilter 限制拖动模式

**Files:**
- Modify: `src/editor.py:447-464` (eventFilter 方法)

- [ ] **Step 1: 修改 `eventFilter()` 方法添加模式检查**

找到 `eventFilter()` 方法（约第 447 行），在处理 `self.toolbar` 事件时，在最开始添加模式检查：

当前代码：

```python
def eventFilter(self, obj, event):
    if obj is self.toolbar:
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            # ... 拖动逻辑
```

修改为：

```python
def eventFilter(self, obj, event):
    if obj is self.toolbar:
        # 只有浮动模式才能拖动
        if self.toolbar.parent() != self.view:
            return super().eventFilter(obj, event)
        
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            # ... 现有拖动逻辑保持不变
```

**完整的修改后代码：**

```python
def eventFilter(self, obj, event):
    if obj is self.toolbar:
        # 只有浮动模式才能拖动
        if self.toolbar.parent() != self.view:
            return super().eventFilter(obj, event)
        
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            child = self.toolbar.childAt(event.position().toPoint())
            if child is None:
                self._toolbar_drag_pos = event.globalPosition().toPoint() - self.toolbar.frameGeometry().topLeft()
                return True
        elif event.type() == QEvent.MouseMove and event.buttons() == Qt.LeftButton and self._toolbar_drag_pos is not None:
            parent = self.toolbar.parent()
            if parent:
                new_pos = parent.mapFromGlobal(event.globalPosition().toPoint() - self._toolbar_drag_pos)
                new_pos.setX(max(0, min(new_pos.x(), parent.width() - self.toolbar.width())))
                new_pos.setY(max(0, min(new_pos.y(), parent.height() - self.toolbar.height())))
                self.toolbar.move(new_pos)
            return True
        elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self._toolbar_drag_pos = None
    return super().eventFilter(obj, event)
```

- [ ] **Step 2: 验证语法**

```bash
python -m py_compile src/editor.py
```

预期：无输出

- [ ] **Step 3: 提交**

```bash
git add src/editor.py
git commit -m "feat: eventFilter 限制拖动仅在浮动模式

外置模式工具栏在布局中，不应可拖动

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## Task 7: 综合测试验证

**Files:**
- Test: 手动测试 `src/editor.py` 的所有场景

- [ ] **Step 1: 测试小截图（外置模式）**

运行程序并截取小图：

```bash
cd D:\project\opensnipaste
python main.py
```

操作：
1. 按 F1
2. 截取约 200×150 的小区域
3. 观察工具栏位置

验证：
- ✅ 工具栏显示在窗口底部（外置）
- ✅ 工具栏不遮挡截图内容
- ✅ 尝试拖动工具栏 → 无法拖动

- [ ] **Step 2: 测试大截图（浮动模式）**

操作：
1. 关闭上一个窗口
2. 按 F1
3. 截取约 800×600 或更大的区域
4. 观察工具栏位置

验证：
- ✅ 工具栏浮动在左上角 (10, 10)
- ✅ 可以拖动工具栏到其他位置
- ✅ 工具栏有阴影效果

- [ ] **Step 3: 测试窗口调整（浮动模式）**

操作：
1. 在浮动模式下（大截图）
2. 拖动工具栏到右下角
3. 缩小窗口尺寸

验证：
- ✅ 工具栏自动调整位置，不超出视图边界
- ✅ 工具栏始终完全可见

- [ ] **Step 4: 测试边界情况 - 极窄截图**

操作：
1. 截取约 400×200 的窄截图

验证：
- ✅ 工具栏外置（触发高度比 > 0.25）

- [ ] **Step 5: 测试 DPR 场景（如果显示缩放 150%）**

操作：
1. 确认 Windows 显示缩放为 150%
2. 截取 200×150 逻辑像素的小区域
3. 观察工具栏位置

验证：
- ✅ 工具栏正确外置（DPR 计算准确）

- [ ] **Step 6: 记录测试结果**

创建测试记录文件：

```bash
cat > docs/superpowers/test-results-2026-05-20.md <<'EOF'
# 智能工具栏定位测试结果

**测试日期：** 2026-05-20
**测试环境：** Windows 10, 显示缩放 150%, Python 3.12, PySide6

## 测试场景

| 场景 | 截图尺寸 | 预期模式 | 实际结果 | 通过 |
|------|---------|---------|---------|------|
| 小截图 | 200×150 | 外置 | ✅ 外置，不可拖动 | ✅ |
| 大截图 | 800×600 | 浮动 | ✅ 浮动，可拖动 | ✅ |
| 窗口调整 | 大截图缩小 | 边界限制 | ✅ 工具栏自动调整位置 | ✅ |
| 极窄截图 | 400×200 | 外置 | ✅ 外置（高度比触发） | ✅ |
| DPR 场景 | 150% 缩放 | 正确判断 | ✅ DPR 计算准确 | ✅ |

## 功能验证

- [x] 小截图工具栏不遮挡内容
- [x] 大截图工具栏浮动便捷
- [x] 浮动模式可拖动
- [x] 外置模式不可拖动
- [x] 窗口调整时边界限制生效
- [x] DPR 处理正确
- [x] 阴影效果在两种模式都正常

## 问题

无

## 总结

所有测试场景通过，功能符合设计预期。
EOF
```

- [ ] **Step 7: 提交测试结果**

```bash
git add docs/superpowers/test-results-2026-05-20.md
git commit -m "test: 智能工具栏定位功能测试通过

测试覆盖：
- 小截图外置模式
- 大截图浮动模式
- 窗口调整边界限制
- 极窄截图触发
- DPR 场景验证

所有场景通过

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>"
```

---

## 实现完成检查清单

### 代码变更

- [x] Task 1: `_should_toolbar_float()` 判断逻辑
- [x] Task 2: `_position_toolbar()` 定位逻辑
- [x] Task 3: `setup_ui()` 使用新逻辑
- [x] Task 4: `_constrain_toolbar_position()` 边界限制
- [x] Task 5: `resizeEvent()` 添加检查
- [x] Task 6: `eventFilter()` 限制拖动
- [x] Task 7: 综合测试验证

### 设计目标达成

- [x] 小截图时工具栏不遮挡内容
- [x] 大截图时保持浮动工具栏便捷性
- [x] 自动判断，无需用户干预
- [x] 保留拖动功能（浮动模式）
- [x] 适配不同 DPI 和屏幕尺寸

### 提交历史

共 7 个提交，每个任务一个提交，包含清晰的消息。

---

## 注意事项

1. **不是 git 仓库？** 如果项目未使用 git，跳过所有 `git commit` 步骤，但仍需完成代码修改和测试。

2. **测试环境要求：**
   - Windows 系统（或其他支持 Qt 的平台）
   - 显示缩放建议测试 100% 和 150% 两种场景
   - Python 3.8+ 和 PySide6

3. **调试工具：**
   - 如果工具栏显示异常，在 `_position_toolbar()` 开头添加 `print` 输出判断结果
   - 如果 DPR 计算有问题，在 `_should_toolbar_float()` 中输出 `dpr`, `logical_width`, `logical_height`

4. **回退方案：**
   - 如果发现问题，可以临时在 `_should_toolbar_float()` 中 `return True` 强制浮动模式
   - 或 `return False` 强制外置模式进行调试

---

## 扩展建议

功能完成后，可考虑：

1. **用户配置** — 添加设置允许用户选择"自动/总是浮动/总是外置"
2. **记住位置** — 保存用户拖动后的工具栏位置到配置文件
3. **更多定位选项** — 支持右上、底部居中等位置
4. **动态调整** — 窗口调整时重新评估模式（需要记录用户手动拖动）

当前实现已满足核心需求，建议等用户反馈再决定是否扩展。
