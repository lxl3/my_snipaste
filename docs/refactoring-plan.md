# MySnipaste 重构计划

> 创建日期：2024-06-08  
> 状态：规划中

---

## 目录

1. [项目现状分析](#项目现状分析)
2. [重构目标](#重构目标)
3. [详细方案](#详细方案)
4. [实施计划](#实施计划)
5. [进度追踪](#进度追踪)

---

## 项目现状分析

### 代码规模统计

| 文件 | 行数 | 方法数 | 状态 |
|------|------|--------|------|
| `src/ui/settings_dialog.py` | 1873 | 51 | ⚠️ 需拆分 |
| `src/overlay/toolbar.py` | 1221 | 61 | ⚠️ 需拆分 |
| `src/ui/pin_window.py` | 1196 | 48 | 📝 可优化 |
| `src/overlay/widget.py` | 1000 | - | 📝 可优化 |
| `src/app.py` | 849 | 32 | 📝 可优化 |
| `src/overlay/actions.py` | 778 | - | ✅ 合理 |
| `src/core/theme.py` | 462 | - | 📝 可整合 |

### 架构模式

**已采用的良好模式：**
- ✅ Mixin 模式分离关注点 (overlay: actions, drawing, rendering, selection)
- ✅ 单例设置管理 (AppSettings)
- ✅ 主题令牌系统 (theme tokens)
- ✅ 国际化支持 (i18n)

**需要改进的问题：**
- ❌ 设置对话框单文件过大，难以维护
- ❌ 工具栏构建代码重复，每个菜单结构相似
- ❌ overlay 和 pin_window 标注逻辑重复实现
- ❌ 全局函数调用散落 (`get_settings()` 21处, `_()` 23处)
- ❌ 主题相关代码分散在多个文件

### 目录结构现状

```
src/
├── app.py                 # 主应用 (849行)
├── core/                  # 核心模块
│   ├── constants.py       # 常量定义
│   ├── glass_effect.py    # 毛玻璃效果
│   ├── hotkeys.py         # 全局热键
│   ├── i18n.py            # 国际化
│   ├── logger.py          # 日志
│   ├── permissions.py     # 权限检查 (macOS)
│   ├── qss_base.py        # QSS 基础样式
│   ├── screenshot_history.py  # 截图历史
│   ├── settings.py        # 设置管理
│   ├── theme.py           # 主题管理
│   ├── utils.py           # 工具函数
│   └── window_detector.py # 窗口检测
├── ocr/                   # OCR 模块
│   └── engine.py          # Tesseract 封装
├── overlay/               # 截图覆盖层
│   ├── widget.py          # 主 Widget (1000行)
│   ├── toolbar.py         # 工具栏 (1221行)
│   ├── actions.py         # 操作 Mixin
│   ├── drawing.py         # 绘制 Mixin
│   ├── rendering.py       # 渲染 Mixin
│   ├── selection.py       # 选择 Mixin
│   ├── ocr_mixin.py       # OCR Mixin
│   └── hotkey_panel.py    # 快捷键面板
├── resources/             # 资源文件
│   ├── icons/toolbar_icons.py  # SVG 图标
│   └── locales/           # 翻译文件
└── ui/                    # UI 组件
    ├── pin_window.py      # Pin 窗口 (1196行)
    ├── pin_actions.py     # Pin 操作 Mixin
    ├── pin_rendering.py   # Pin 渲染 Mixin
    ├── settings_dialog.py # 设置对话框 (1873行)
    ├── tray.py            # 系统托盘
    ├── toast.py           # Toast 通知
    ├── color_picker.py    # 取色器
    └── ...                # 其他对话框
```

---

## 重构目标

### 核心目标

1. **可维护性**：单文件不超过 500 行，单方法不超过 50 行
2. **可复用性**：消除 overlay/pin_window 之间的重复代码
3. **可扩展性**：新增工具/设置项时只需添加配置，无需修改框架代码
4. **可测试性**：核心逻辑与 UI 解耦，便于单元测试

### 非目标

- 不改变用户可见的功能和交互
- 不引入新的外部依赖
- 不进行大规模 API 变更

---

## 详细方案

### 方案一：设置对话框模块化

**目标**：将 1873 行的 `settings_dialog.py` 拆分为独立 Tab 模块

**目标结构：**
```
src/ui/settings/
├── __init__.py            # 导出 SettingsDialog
├── dialog.py              # 主对话框框架 (~200行)
├── search.py              # 设置搜索功能
├── import_export.py       # 导入导出功能
├── tabs/
│   ├── __init__.py
│   ├── base_tab.py        # Tab 基类，定义接口
│   ├── general_tab.py     # 通用：语言、主题、启动
│   ├── capture_tab.py     # 截图：延迟、声音、光标、后续动作
│   ├── save_tab.py        # 保存：目录、格式
│   ├── annotation_tab.py  # 标注：颜色、线宽、字体
│   ├── ocr_tab.py         # OCR：引擎、语言
│   ├── shortcuts_tab.py   # 快捷键：全局、工具
│   └── advanced_tab.py    # 高级：日志、权限
└── widgets/
    ├── __init__.py
    ├── hotkey_recorder.py # 已有，移动到此
    ├── color_button.py    # 颜色选择按钮
    └── path_selector.py   # 路径选择器
```

**Tab 基类设计：**
```python
class BaseSettingsTab(QWidget):
    """设置页签基类"""
    
    # 子类必须定义
    tab_id: str           # 唯一标识，用于搜索
    tab_name: str         # 显示名称
    tab_icon: str         # 图标名称
    
    def __init__(self, settings: AppSettings):
        self.settings = settings
    
    @abstractmethod
    def load_settings(self) -> None:
        """从 settings 加载值到 UI"""
        pass
    
    @abstractmethod
    def save_settings(self) -> None:
        """从 UI 保存值到 settings"""
        pass
    
    @abstractmethod
    def reset_to_defaults(self) -> None:
        """重置为默认值"""
        pass
    
    def get_searchable_items(self) -> list[tuple[str, QWidget]]:
        """返回可搜索的 (关键词, 控件) 列表"""
        return []
```

**预计收益：**
- 每个 Tab 文件约 150-250 行，易于维护
- 新增设置项只需修改对应 Tab
- 可独立测试每个 Tab 的逻辑

**实施步骤：**
- [ ] 1.1 创建目录结构和基类
- [ ] 1.2 提取 GeneralTab (语言、主题、启动)
- [ ] 1.3 提取 CaptureTab (截图行为)
- [ ] 1.4 提取 SaveTab (保存设置)
- [ ] 1.5 提取 AnnotationTab (标注样式)
- [ ] 1.6 提取 OcrTab (OCR 设置)
- [ ] 1.7 提取 ShortcutsTab (快捷键)
- [ ] 1.8 提取 AdvancedTab (日志、权限)
- [ ] 1.9 重构主对话框，动态加载 Tab
- [ ] 1.10 迁移搜索和导入导出功能

---

### 方案二：工具栏声明式重构

**目标**：将 1221 行的 `toolbar.py` 改为声明式配置 + 构建器模式

**目标结构：**
```
src/overlay/toolbar/
├── __init__.py            # 导出 OverlayToolbar
├── toolbar.py             # 主工具栏类 (~200行)
├── builder.py             # 工具栏构建器
├── config.py              # 工具声明式配置
├── menus/
│   ├── __init__.py
│   ├── base_menu.py       # 菜单基类
│   ├── shape_menu.py      # 形状菜单
│   ├── arrow_menu.py      # 箭头菜单
│   ├── pen_menu.py        # 画笔菜单
│   ├── text_menu.py       # 文字菜单
│   └── ...
└── widgets/
    ├── color_picker.py    # 颜色选择器
    ├── width_slider.py    # 宽度滑块
    └── style_combo.py     # 样式下拉框
```

**声明式配置示例：**
```python
# config.py
TOOLBAR_CONFIG = [
    {
        "id": "shape",
        "icon": "rectangle",
        "tooltip": "Shape (Rectangle / Ellipse)",
        "tools": ["rect", "ellipse"],
        "default_tool": "rect",
        "options": [
            {"type": "color_picker"},
            {"type": "color_buttons", "colors": PRESET_COLORS},
        ]
    },
    {
        "id": "arrow", 
        "icon": "arrow",
        "tooltip": "Arrow (Arrow / Line)",
        "tools": [
            {"id": "arrow", "type": "style_combo", "styles": [
                ("solid", "arrow_solid", "Solid"),
                ("hollow", "arrow_hollow", "Hollow"),
                ("solid_tail", "arrow_solid_tail", "Solid Tail"),
                ("hollow_tail", "arrow_hollow_tail", "Hollow Tail"),
            ]},
            {"id": "line", "icon": "line", "label": "Line"},
        ],
        "default_tool": "arrow",
        "options": [
            {"type": "color_picker"},
            {"type": "color_buttons", "colors": PRESET_COLORS},
        ]
    },
    # ... 更多工具
]
```

**预计收益：**
- 新增工具只需添加配置，无需写 UI 代码
- 工具栏外观一致性自动保证
- 配置可序列化，支持用户自定义工具栏

**实施步骤：**
- [ ] 2.1 设计配置格式和数据结构
- [ ] 2.2 实现 ToolbarBuilder 基础框架
- [ ] 2.3 提取通用组件 (颜色按钮、分隔线等)
- [ ] 2.4 迁移形状菜单
- [ ] 2.5 迁移箭头菜单
- [ ] 2.6 迁移画笔菜单
- [ ] 2.7 迁移其他菜单
- [ ] 2.8 清理旧代码

---

### 方案三：统一标注系统

**目标**：消除 overlay 和 pin_window 之间的标注逻辑重复

**目标结构：**
```
src/annotations/
├── __init__.py
├── models.py              # 标注数据模型
├── renderer.py            # 标注渲染器
├── editor.py              # 标注编辑器 (选中、拖拽、调整)
├── serializer.py          # 序列化/反序列化
├── effects/
│   ├── blur.py            # 模糊效果
│   ├── mosaic.py          # 马赛克效果
│   └── magnifier.py       # 放大镜效果
└── tools/
    ├── base_tool.py       # 工具基类
    ├── rect_tool.py       # 矩形工具
    ├── arrow_tool.py      # 箭头工具
    └── ...
```

**标注模型设计：**
```python
# models.py
from dataclasses import dataclass
from typing import Union
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor

@dataclass
class BaseAnnotation:
    """标注基类"""
    type: str
    color: QColor
    width: int
    
    def bounds(self) -> QRectF:
        """返回包围盒"""
        raise NotImplementedError
    
    def contains(self, point: QPointF) -> bool:
        """点击测试"""
        raise NotImplementedError
    
    def translate(self, dx: float, dy: float) -> None:
        """平移"""
        raise NotImplementedError

@dataclass
class RectAnnotation(BaseAnnotation):
    rect: QRectF
    
    def bounds(self) -> QRectF:
        return self.rect
    
    def contains(self, point: QPointF) -> bool:
        # 检测边框区域
        ...

@dataclass
class ArrowAnnotation(BaseAnnotation):
    start: QPointF
    end: QPointF
    style: str = "solid"  # solid, hollow, solid_tail, hollow_tail
    
    def bounds(self) -> QRectF:
        return QRectF(self.start, self.end).normalized()
```

**预计收益：**
- 标注逻辑单点维护
- overlay 和 pin_window 共用同一套渲染/编辑代码
- 易于添加新标注类型
- 便于单元测试

**实施步骤：**
- [ ] 3.1 设计标注数据模型
- [ ] 3.2 实现统一渲染器
- [ ] 3.3 实现编辑器 (选中、拖拽)
- [ ] 3.4 迁移 overlay 使用新系统
- [ ] 3.5 迁移 pin_window 使用新系统
- [ ] 3.6 删除重复代码

---

### 方案四：依赖注入改进

**目标**：减少全局函数调用，提高可测试性

**当前问题：**
```python
# 散落在各处的全局调用
from ..core.settings import get_settings
from ..core.i18n import _
from ..core.theme import theme

s = get_settings()  # 21 处
_("text")           # 23 处
theme.get("key")    # 多处
```

**改进方案：**
```python
# context.py
@dataclass
class AppContext:
    settings: AppSettings
    theme: ThemeManager
    i18n: I18nManager
    history: ScreenshotHistory
    
    @classmethod
    def create(cls) -> "AppContext":
        return cls(
            settings=get_settings(),
            theme=ThemeManager(),
            i18n=I18nManager(),
            history=ScreenshotHistory(),
        )

# 组件通过构造函数接收
class PinWindow(QWidget):
    def __init__(self, ctx: AppContext, pixmap: QPixmap):
        self.ctx = ctx
        # 使用 self.ctx.settings 代替 get_settings()
        # 使用 self.ctx.i18n.t("key") 代替 _("key")
```

**实施步骤：**
- [ ] 4.1 创建 AppContext 类
- [ ] 4.2 在 app.py 初始化 context
- [ ] 4.3 逐步迁移组件使用 context
- [ ] 4.4 添加测试用 MockContext

---

### 方案五：主题系统整合

**目标**：整合分散的主题相关代码

**当前分布：**
- `core/theme.py` - 主题管理器、令牌
- `core/qss_base.py` - QSS 样式
- `core/glass_effect.py` - 毛玻璃效果

**目标结构：**
```
src/core/theme/
├── __init__.py        # 导出 ThemeManager, theme
├── manager.py         # 主题管理器
├── tokens.py          # 设计令牌定义
├── qss.py             # QSS 生成器
└── effects.py         # 视觉效果 (毛玻璃等)
```

**实施步骤：**
- [ ] 5.1 创建 theme 子包
- [ ] 5.2 迁移 ThemeManager
- [ ] 5.3 迁移 tokens
- [ ] 5.4 迁移 qss 生成
- [ ] 5.5 迁移 glass_effect
- [ ] 5.6 更新所有导入

---

## 实施计划

### 阶段规划

| 阶段 | 方案 | 预计工时 | 风险等级 | 依赖 |
|------|------|----------|----------|------|
| **Phase 1** | 设置对话框模块化 | 2-3 天 | 低 | 无 |
| **Phase 2** | 工具栏声明式重构 | 2-3 天 | 中 | 无 |
| **Phase 3** | 统一标注系统 | 3-5 天 | 高 | 无 |
| **Phase 4** | 依赖注入改进 | 1-2 天 | 低 | 无 |
| **Phase 5** | 主题系统整合 | 1-2 天 | 低 | 无 |

### 建议执行顺序

1. **先做 Phase 1 (设置对话框)**：风险最低，收益明显
2. **再做 Phase 2 (工具栏)**：巩固模块化思路
3. **Phase 4, 5 可并行**：独立性强
4. **最后做 Phase 3 (标注系统)**：影响范围最大，需要充分测试

---

## 进度追踪

### Phase 1: 设置对话框模块化

| 任务 | 状态 | 完成日期 | 备注 |
|------|------|----------|------|
| 1.1 创建目录结构和基类 | ⬜ 待开始 | | |
| 1.2 提取 GeneralTab | ⬜ 待开始 | | |
| 1.3 提取 CaptureTab | ⬜ 待开始 | | |
| 1.4 提取 SaveTab | ⬜ 待开始 | | |
| 1.5 提取 AnnotationTab | ⬜ 待开始 | | |
| 1.6 提取 OcrTab | ⬜ 待开始 | | |
| 1.7 提取 ShortcutsTab | ⬜ 待开始 | | |
| 1.8 提取 AdvancedTab | ⬜ 待开始 | | |
| 1.9 重构主对话框 | ⬜ 待开始 | | |
| 1.10 迁移搜索和导入导出 | ⬜ 待开始 | | |

### Phase 2: 工具栏声明式重构

| 任务 | 状态 | 完成日期 | 备注 |
|------|------|----------|------|
| 2.1 设计配置格式 | ⬜ 待开始 | | |
| 2.2 实现 ToolbarBuilder | ⬜ 待开始 | | |
| 2.3 提取通用组件 | ⬜ 待开始 | | |
| 2.4-2.7 迁移各菜单 | ⬜ 待开始 | | |
| 2.8 清理旧代码 | ⬜ 待开始 | | |

### Phase 3: 统一标注系统

| 任务 | 状态 | 完成日期 | 备注 |
|------|------|----------|------|
| 3.1 设计标注模型 | ⬜ 待开始 | | |
| 3.2 实现统一渲染器 | ⬜ 待开始 | | |
| 3.3 实现编辑器 | ⬜ 待开始 | | |
| 3.4 迁移 overlay | ⬜ 待开始 | | |
| 3.5 迁移 pin_window | ⬜ 待开始 | | |
| 3.6 删除重复代码 | ⬜ 待开始 | | |

### Phase 4: 依赖注入改进

| 任务 | 状态 | 完成日期 | 备注 |
|------|------|----------|------|
| 4.1 创建 AppContext | ⬜ 待开始 | | |
| 4.2 初始化 context | ⬜ 待开始 | | |
| 4.3 迁移组件 | ⬜ 待开始 | | |
| 4.4 添加 MockContext | ⬜ 待开始 | | |

### Phase 5: 主题系统整合

| 任务 | 状态 | 完成日期 | 备注 |
|------|------|----------|------|
| 5.1 创建 theme 子包 | ⬜ 待开始 | | |
| 5.2-5.5 迁移代码 | ⬜ 待开始 | | |
| 5.6 更新导入 | ⬜ 待开始 | | |

---

## 附录

### A. 代码质量指标目标

| 指标 | 当前 | 目标 |
|------|------|------|
| 最大文件行数 | 1873 | ≤500 |
| 最大方法行数 | ~100 | ≤50 |
| 测试覆盖率 | ~30% | ≥60% |
| 重复代码率 | 未测量 | ≤5% |

### B. 相关文档

- [项目 README](../README.md)
- [贡献指南](../CONTRIBUTING.md) (如有)

### C. 更新记录

| 日期 | 更新内容 |
|------|----------|
| 2024-06-08 | 初始版本，完成现状分析和方案设计 |
