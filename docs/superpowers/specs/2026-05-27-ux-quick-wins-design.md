# MySnipaste UX 快速优化设计文档

**设计日期**: 2026-05-27  
**设计者**: Claude (基于用户需求)  
**版本**: 1.0

---

## 概述

本设计针对 MySnipaste 截图工具的用户体验进行快速优化，重点解决用户反馈的三大痛点：
1. **视觉反馈缺失** - 操作后无明确提示
2. **编辑体验不佳** - 工具设置不记忆、颜色选择不便
3. **历史管理缺失** - 无法查看最近的截图

**目标**: 在 1-2 周内实现高优先级的体验改进，快速提升用户满意度。

---

## 用户需求分析

### 需求来源

通过用户调研，确定了以下最关心的体验问题：

**视觉反馈场景（优先级高 → 低）**:
- ✅ 保存/复制成功提示
- ✅ OCR 识别进度和结果
- ✅ 撤销/重做反馈
- ✅ 快捷键提示
- ✅ 贴图成功提示

**编辑体验痛点（优先级高 → 低）**:
- ✅ 颜色选择不方便（无最近使用颜色）
- ✅ 工具设置不记忆
- ✅ 文字无法重新编辑（后续版本）
- ✅ 标注无法移动/调整（后续版本）
- ✅ 缺少常用工具（后续版本）
- ✅ 标注层级无法调整（后续版本）
- ✅ 精确操作困难（后续版本）

**历史管理需求**:
- ✅ 简单的最近 5-10 张截图缩略图列表

### 排除的功能

以下功能不在本次优化范围内（可能在后续版本考虑）：
- ❌ 标注可编辑（移动、调整大小）
- ❌ 文字重新编辑
- ❌ 新增标注工具（高亮笔、序号等）
- ❌ 层级调整
- ❌ 辅助功能（网格、吸附）
- ❌ 复杂的历史管理（搜索、标签、云同步等）

---

## 功能设计

### 1. Toast 提示系统

#### 1.1 设计目标
为关键操作提供即时、非侵入式的视觉反馈。

#### 1.2 显示规范

**位置**: 截图界面顶部居中  
**原因**: 不遮挡工具栏和标注区域，更容易注意到

**样式规范**:
```
- 背景: 半透明色块 (rgba, 透明度 0.95)
- 圆角: 8px
- 内边距: 12px 20px
- 阴影: 0 4px 12px rgba(0,0,0,0.2)
- 字体: 14px, 500 字重
- 图标: 18px emoji 或 Unicode 符号
```

**颜色方案**:
- 成功操作: `rgba(40, 167, 69, 0.95)` (绿色)
- 一般操作: `rgba(0, 123, 255, 0.95)` (蓝色)
- 错误提示: `rgba(220, 53, 69, 0.95)` (红色) - 如需要

#### 1.3 动画效果

**进场动画** (300ms):
- 从顶部 -50px 滑入到目标位置
- 同时透明度从 0 到 1

**退场动画** (200ms):
- 透明度从 1 到 0
- 位置不变

**显示时长**:
- 默认: 2000ms
- 鼠标悬停: 暂停自动消失
- 移开鼠标: 继续倒计时

#### 1.4 提示消息列表

| 操作 | 提示文本 | 图标 | 颜色 |
|------|---------|------|------|
| 复制成功 | "已复制到剪贴板" | ✓ | 绿色 |
| 保存成功 | "截图已保存" | ✓ | 绿色 |
| 贴图成功 | "已固定到桌面" | 📌 | 绿色 |
| 撤销 | "已撤销" | ↶ | 蓝色 |
| 重做 | "已重做" | ↷ | 蓝色 |
| OCR 进行中 | "OCR 识别中..." | 🔍 | 蓝色 |
| OCR 完成 | "识别完成" + 预览 | ✓ | 绿色 |

#### 1.5 技术实现要点

**组件设计**:
```python
# src/ui/toast.py
class ToastNotification(QWidget):
    """Toast 提示组件"""
    
    def __init__(self, message: str, icon: str, toast_type: str):
        # toast_type: "success", "info", "error"
        pass
    
    def show_toast(self, duration: int = 2000):
        """显示 Toast 并自动消失"""
        pass

class ToastManager:
    """Toast 管理器 - 处理多个 Toast 堆叠"""
    
    _instance = None
    _toasts: list[ToastNotification] = []
    
    @classmethod
    def show(cls, message: str, icon: str = "✓", 
             toast_type: str = "success", duration: int = 2000):
        """显示 Toast 提示"""
        pass
```

**集成点**:
- `src/overlay/actions.py` - 保存/复制/贴图操作后调用
- `src/overlay/widget.py` - 撤销/重做操作后调用
- `src/overlay/ocr_mixin.py` - OCR 开始和完成时调用

---

### 2. 快捷键帮助面板

#### 2.1 设计目标
帮助用户发现和记住所有可用的快捷键，降低学习曲线。

#### 2.2 触发方式

**主动触发**:
- 按键: `?` 或 `F1`
- 再次按下: 关闭面板
- 按 `Esc`: 关闭面板
- 点击面板外: 关闭面板

**被动提示** (首次使用):
- 在工具栏右侧显示提示气泡
- 内容: "💡 按 ? 查看所有快捷键"
- 显示 3 秒后自动消失
- 可点击 × 关闭
- 关闭后记录到配置文件，不再显示

#### 2.3 面板样式

**布局**:
- 半透明白色背景: `rgba(255, 255, 255, 0.92)`
- 毛玻璃效果: `backdrop-filter: blur(10px)`
- 圆角: 6px
- 边框: 1px solid rgba(255,255,255,0.3)
- 阴影: 0 4px 20px rgba(0,0,0,0.15)
- 最大宽度: 350px
- 内边距: 16px 20px

**内容组织**:
- 标题: "快捷键" (14px, 600 字重)
- 分隔线分组
- 每行: 操作名称 + 快捷键 (flex 两端对齐)
- 字体: 13px
- 颜色: #555

#### 2.4 快捷键列表

**基础操作**:
- 复制 - `Ctrl+C`
- 保存 - `Ctrl+S`
- 贴图 - `Ctrl+P`
- 完成 - `Enter`
- 取消 - `Esc`

**编辑操作**:
- 撤销 - `Ctrl+Z`
- 重做 - `Ctrl+Y`

**选区调整**:
- 微调 - `方向键` (1px)
- 快速调整 - `Shift+方向键` (10px)

**工具快捷键** (可选，后续添加):
- 矩形 - `R`
- 画笔 - `P`
- 文字 - `T`
- 橡皮擦 - `E`

**其他**:
- 显示此帮助 - `? / F1`

#### 2.5 技术实现要点

```python
# src/overlay/hotkey_panel.py
class HotkeyHelpPanel(QWidget):
    """快捷键帮助面板"""
    
    def __init__(self, parent):
        # 设置半透明背景和样式
        pass
    
    def show_panel(self):
        """显示面板并居中"""
        pass
    
    def hide_panel(self):
        """隐藏面板"""
        pass

# src/overlay/widget.py - 添加按键监听
def keyPressEvent(self, event):
    if event.key() == Qt.Key_Question or event.key() == Qt.Key_F1:
        self._toggle_hotkey_panel()
```

---

### 3. 颜色记忆功能

#### 3.1 设计目标
减少重复选择相同颜色的操作，提升绘制效率。

#### 3.2 UI 布局

**工具栏颜色区域**:
```
[当前] | [最近1] [最近2] [最近3] | [预设1] [预设2] ... [取色器+]
```

**视觉区分**:
- 当前颜色: 加粗边框 (2px solid #333)
- 最近使用: 普通边框 (1px solid #999), 透明度 0.9
- 预设颜色: 浅色边框 (1px solid #ccc)
- 分隔线: 1px 灰色竖线

#### 3.3 记忆逻辑

**记录时机**:
- 用户从预设颜色中选择
- 用户从取色器中选择自定义颜色

**记录规则**:
- 最多记录 5 个最近使用的颜色
- 相同颜色不重复记录（去重）
- 新颜色插入到列表开头
- 超过 5 个时删除最旧的

**持久化**:
```json
// settings.json
{
  "recent_colors": [
    "#ffc107",
    "#007bff",
    "#28a745",
    "#ff3232",
    "#6c757d"
  ]
}
```

#### 3.4 技术实现要点

```python
# src/core/settings.py - 添加字段
@dataclass
class AppSettings:
    # ... 现有字段
    recent_colors: list[str] = field(default_factory=list)
    
    def add_recent_color(self, color: str):
        """添加颜色到最近使用列表"""
        if color in self.recent_colors:
            self.recent_colors.remove(color)
        self.recent_colors.insert(0, color)
        if len(self.recent_colors) > 5:
            self.recent_colors = self.recent_colors[:5]
        self.save()

# src/overlay/toolbar.py - 更新颜色选择器
def _build_color_buttons(self, layout):
    """构建颜色按钮，包括最近使用"""
    settings = get_settings()
    
    # 添加最近使用的颜色
    for color in settings.recent_colors[:3]:
        btn = self._make_color_button(color)
        layout.addWidget(btn)
    
    # 添加分隔线
    # 添加预设颜色
    # ...
```

---

### 4. 历史截图列表

#### 4.1 设计目标
提供快速访问最近截图的能力，无需复杂的管理功能。

#### 4.2 入口设计

**位置**: 系统托盘菜单
**菜单项**: "📂 最近截图" → 子菜单展开

**子菜单内容**:
- 显示最近 10 张截图的缩略图列表
- 每项包含: 缩略图 (48×36px) + 时间戳 + 尺寸
- 点击操作（见下文）

#### 4.3 缩略图生成

**规格**:
- 尺寸: 48×36px (4:3 比例)
- 缩放算法: 高质量缩放 (Qt.SmoothTransformation)
- 缓存: 生成后缓存到内存，避免重复计算

**时间显示**:
- 刚才 (< 1 分钟)
- X 分钟前 (< 60 分钟)
- X 小时前 (< 24 小时)
- X 天前 (>= 24 小时)

#### 4.4 交互设计

**点击操作**:
- 左键单击: 复制该截图到剪贴板
- 中键点击 / Ctrl+左键: 重新打开编辑（在新的 CaptureOverlay 中加载）
- 右键: 显示上下文菜单
  - 复制
  - 另存为...
  - 从历史中删除

**鼠标悬停**:
- 高亮显示当前项
- 可选: 显示更大的预览 (Tooltip)

#### 4.5 数据存储

**存储位置**:
```
~/.config/MySnipaste/history/
├── 20260527_143022.png  # 截图文件
├── 20260527_143045.png
├── ...
└── history.json         # 元数据
```

**元数据格式**:
```json
{
  "screenshots": [
    {
      "id": "20260527_143022",
      "filename": "20260527_143022.png",
      "timestamp": 1779860622,
      "width": 1920,
      "height": 1080,
      "has_annotations": true
    }
  ],
  "max_count": 100
}
```

**自动清理**:
- 保留最近 100 张截图
- 超过时自动删除最旧的
- 启动时检查并清理

#### 4.6 技术实现要点

```python
# src/core/screenshot_history.py
class ScreenshotHistory:
    """截图历史管理"""
    
    def __init__(self):
        self.history_dir = Path.home() / ".config/MySnipaste/history"
        self.history_file = self.history_dir / "history.json"
        self.max_count = 100
    
    def add_screenshot(self, pixmap: QPixmap, has_annotations: bool):
        """添加截图到历史"""
        # 生成唯一文件名
        # 保存截图文件
        # 更新元数据
        # 清理旧截图
        pass
    
    def get_recent(self, count: int = 10) -> list[dict]:
        """获取最近的截图"""
        pass
    
    def get_thumbnail(self, screenshot_id: str) -> QPixmap:
        """获取缩略图（带缓存）"""
        pass
    
    def delete_screenshot(self, screenshot_id: str):
        """从历史中删除"""
        pass

# src/ui/tray.py - 添加历史菜单
def _build_history_menu(self):
    """构建历史截图子菜单"""
    history = ScreenshotHistory()
    recent = history.get_recent(10)
    
    for item in recent:
        action = QAction(f"{item['time_ago']} - {item['width']}×{item['height']}")
        action.triggered.connect(lambda checked, id=item['id']: self._on_history_click(id))
        menu.addAction(action)
```

---

### 5. 工具设置记忆

#### 5.1 设计目标
记住用户的工具偏好，避免每次截图都要重新设置。

#### 5.2 记忆内容

**全局设置** (跨工具):
- 上次使用的工具 (矩形/箭头/画笔等)

**每个工具的独立设置**:
- 颜色
- 线条粗细
- 是否填充 (矩形/圆形)
- 字体设置 (文字工具)
  - 字体名称
  - 字号
  - 加粗/斜体状态

#### 5.3 数据结构

```json
{
  "last_tool": "rect",
  "tool_settings": {
    "rect": {
      "color": "#ff3232",
      "width": 3,
      "filled": false
    },
    "ellipse": {
      "color": "#007bff",
      "width": 3,
      "filled": false
    },
    "arrow": {
      "color": "#28a745",
      "width": 2
    },
    "pen": {
      "color": "#000000",
      "width": 3
    },
    "text": {
      "color": "#000000",
      "font_family": "Segoe UI",
      "font_size": 20,
      "bold": false,
      "italic": false
    }
  }
}
```

#### 5.4 保存时机

**读取**:
- 应用启动时加载配置
- 创建 CaptureOverlay 时应用设置

**保存**:
- 切换工具时保存当前工具的设置
- 修改颜色/粗细时立即保存
- 关闭 CaptureOverlay 时保存当前工具

#### 5.5 技术实现要点

```python
# src/core/settings.py - 添加工具设置
@dataclass
class ToolSettings:
    color: str = "#ff3232"
    width: int = 3
    filled: bool = False
    font_family: str = "Segoe UI"
    font_size: int = 20
    bold: bool = False
    italic: bool = False

@dataclass
class AppSettings:
    # ... 现有字段
    last_tool: str = "select"
    tool_settings: dict[str, dict] = field(default_factory=dict)
    
    def get_tool_settings(self, tool: str) -> dict:
        """获取工具设置"""
        return self.tool_settings.get(tool, {})
    
    def save_tool_settings(self, tool: str, settings: dict):
        """保存工具设置"""
        self.tool_settings[tool] = settings
        self.save()

# src/overlay/widget.py - 应用和保存设置
def __init__(self):
    settings = get_settings()
    
    # 恢复上次的工具
    self.current_tool = settings.last_tool
    
    # 恢复工具设置
    tool_settings = settings.get_tool_settings(self.current_tool)
    self.current_color = QColor(tool_settings.get("color", "#ff3232"))
    self.current_width = tool_settings.get("width", 3)
    # ...

def _set_tool(self, tool: str):
    """切换工具时保存当前工具设置"""
    settings = get_settings()
    
    # 保存当前工具的设置
    settings.save_tool_settings(self.current_tool, {
        "color": self.current_color.name(),
        "width": self.current_width,
        # ...
    })
    
    # 切换到新工具
    self.current_tool = tool
    settings.last_tool = tool
    settings.save()
    
    # 恢复新工具的设置
    tool_settings = settings.get_tool_settings(tool)
    self.current_color = QColor(tool_settings.get("color", "#ff3232"))
    # ...
```

---

## 技术架构

### 文件结构

```
src/
├── ui/
│   ├── toast.py                 # NEW: Toast 提示组件
│   └── tray.py                  # MODIFIED: 添加历史菜单
├── overlay/
│   ├── widget.py                # MODIFIED: 集成新功能
│   ├── hotkey_panel.py          # NEW: 快捷键帮助面板
│   ├── actions.py               # MODIFIED: 添加 Toast 调用
│   └── toolbar.py               # MODIFIED: 颜色记忆 UI
├── core/
│   ├── settings.py              # MODIFIED: 新增配置字段
│   └── screenshot_history.py    # NEW: 历史管理
└── resources/
    └── locales/
        ├── zh_CN.json           # MODIFIED: 新增翻译
        └── en_US.json           # MODIFIED: 新增翻译
```

### 依赖关系

```
CaptureOverlay
  ├─→ ToastManager (显示提示)
  ├─→ HotkeyHelpPanel (快捷键帮助)
  ├─→ ScreenshotHistory (保存历史)
  └─→ AppSettings (读写配置)

TrayManager
  └─→ ScreenshotHistory (显示历史菜单)
```

---

## 国际化

### 新增翻译键

**Toast 提示**:
- `"Copied to clipboard"` → `"已复制到剪贴板"`
- `"Screenshot saved"` → `"截图已保存"`
- `"Pinned to desktop"` → `"已固定到桌面"`
- `"Undone"` → `"已撤销"`
- `"Redone"` → `"已重做"`
- `"OCR recognizing..."` → `"OCR 识别中..."`
- `"Recognition complete"` → `"识别完成"`

**快捷键帮助**:
- `"Hotkeys"` → `"快捷键"`
- `"Copy"` → `"复制"`
- `"Save"` → `"保存"`
- `"Pin"` → `"贴图"`
- `"Undo"` → `"撤销"`
- `"Redo"` → `"重做"`
- `"Press Esc to close"` → `"按 Esc 关闭"`

**历史菜单**:
- `"Recent Screenshots"` → `"最近截图"`
- `"just now"` → `"刚才"`
- `"{n} minutes ago"` → `"{n} 分钟前"`
- `"{n} hours ago"` → `"{n} 小时前"`
- `"{n} days ago"` → `"{n} 天前"`
- `"Delete from history"` → `"从历史中删除"`
- `"Save as..."` → `"另存为..."`

---

## 配置选项

### 新增设置项

```python
@dataclass
class AppSettings:
    # 视觉反馈
    enable_toast: bool = True
    toast_duration: int = 2000  # 毫秒
    
    # 快捷键帮助
    show_hotkey_tip: bool = True  # 首次提示
    
    # 颜色记忆
    recent_colors: list[str] = field(default_factory=list)
    max_recent_colors: int = 5
    
    # 历史截图
    enable_history: bool = True
    history_max_count: int = 100
    auto_save_to_history: bool = True  # 可选：所有截图自动保存
    
    # 工具设置
    last_tool: str = "select"
    tool_settings: dict[str, dict] = field(default_factory=dict)
```

### 设置界面

在设置对话框中添加新的选项卡或分组：

**"用户体验"标签页**:
- ☑ 启用操作提示 (Toast)
- 提示显示时长: [2000] 毫秒
- ☑ 显示快捷键提示气泡（首次）
- ☑ 启用截图历史
- ☑ 自动保存所有截图到历史
- 历史保留数量: [100] 张

---

## 性能考虑

### Toast 系统
- **内存**: 每个 Toast 约 1KB，最多 3 个同时显示
- **CPU**: 动画使用 QPropertyAnimation，GPU 加速
- **优化**: 超过 3 个时自动移除最旧的

### 历史截图
- **磁盘空间**: 
  - 每张截图平均 200KB
  - 100 张约 20MB
- **启动时间**: 
  - 加载元数据: ~10ms
  - 不影响启动速度
- **优化**: 
  - 缩略图按需生成并缓存
  - 异步加载，不阻塞 UI

### 工具设置
- **内存**: 所有工具设置 < 1KB
- **I/O**: 仅在修改时写入，使用节流（200ms 防抖）

---

## 测试策略

### 单元测试

```python
# tests/test_toast.py
def test_toast_show_and_hide():
    """测试 Toast 显示和隐藏"""
    
def test_toast_stacking():
    """测试多个 Toast 堆叠"""

# tests/test_screenshot_history.py
def test_add_screenshot():
    """测试添加截图到历史"""
    
def test_auto_cleanup():
    """测试自动清理旧截图"""
    
def test_get_recent():
    """测试获取最近截图"""

# tests/test_settings_memory.py
def test_tool_settings_save_load():
    """测试工具设置保存和加载"""
    
def test_recent_colors():
    """测试颜色记忆"""
```

### 集成测试

1. **完整截图流程** + Toast:
   - 截图 → 标注 → 保存 → 验证 Toast 显示
   - 截图 → 标注 → 复制 → 验证 Toast 显示
   - 截图 → 标注 → 贴图 → 验证 Toast 显示

2. **工具设置记忆**:
   - 选择工具A → 设置颜色/粗细 → 关闭
   - 重新截图 → 验证工具A的设置已恢复

3. **历史列表**:
   - 连续截图 5 次
   - 打开托盘菜单 → 验证显示 5 张缩略图
   - 点击第 3 张 → 验证复制成功

### 手动测试

- [ ] Toast 动画流畅度
- [ ] 快捷键帮助面板显示正确
- [ ] 颜色记忆去重逻辑
- [ ] 历史缩略图清晰度
- [ ] 跨平台兼容性 (Windows/macOS)
- [ ] 多语言显示正确

---

## 兼容性

### 平台支持
- ✅ Windows 10/11
- ✅ macOS 12+
- ✅ Linux (Ubuntu 20.04+)

### 向后兼容
- 新增配置字段提供默认值
- 旧版本配置文件自动升级
- 历史功能可选，不影响现有用户

---

## 实施计划

### 阶段 1: 核心功能（3-5天）
1. Toast 提示系统
2. 快捷键帮助面板
3. 单元测试

### 阶段 2: 记忆功能（2-3天）
4. 颜色记忆
5. 工具设置记忆
6. 持久化逻辑

### 阶段 3: 历史管理（2-3天）
7. 历史存储
8. 托盘菜单集成
9. 缩略图生成

### 阶段 4: 完善（1-2天）
10. 国际化翻译
11. 集成测试
12. 文档更新

**总计**: 8-13 天（约 1-2 周）

---

## 后续优化方向

本设计完成后，可根据用户反馈考虑以下增强：

1. **编辑增强** (后续版本):
   - 标注可移动和调整大小
   - 文字双击重新编辑
   - 层级调整（上移/下移）
   - 新增标注工具（高亮笔、序号标记等）

2. **辅助功能** (后续版本):
   - 网格对齐
   - 吸附功能
   - 标尺和参考线

3. **历史增强** (可选):
   - 搜索和筛选
   - 标签分类
   - 批量操作

---

## 附录

### 参考资料
- 现有代码库: `src/overlay/`, `src/ui/`
- 架构文档: `docs/ARCHITECTURE.md`
- 用户调研结果: (本设计文档第 2 节)

### 变更历史
- 2026-05-27: 初始版本，基于用户需求调研