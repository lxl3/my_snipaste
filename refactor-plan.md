# openSnipaste 重构计划

## Goal
消除架构债务：死代码、不一致导入、上帝类，不引入新功能。

---

## Phase 1: 清理死代码

### Task 1.1: 移除旧 HotkeyListener
移除 `core/hotkeys.py` 中已被 `MultiHotkeyListener` 取代的 `HotkeyListener` 和 `_PynputListener` 类（~200 行死代码）。
- Verify: `git grep 'HotkeyListener('` 只保留 `MultiHotkeyListener` 引用

### Task 1.2: 验证再无引用旧类
`git grep` 检查 `HotkeyListener` 和 `_PynputListener` 在项目中的残余引用。

---

## Phase 2: 统一主题导入

### Task 2.1: 审计不一致的 theme import
当前混用三种模式：
- `from .core.theme_pkg import theme as theme_manager`
- `from ..core.theme_pkg import theme as _tw`
- `from .core.theme_pkg import theme as theme_mgr`

统一为 `from ...core.theme_pkg import theme`。

### Task 2.2: 统一 theme 模块级快捷方式使用
`theme.py` 底部有模块级快捷方式 `get=theme.get`, `qss=theme.qss`，但已经通过 `theme_pkg/__init__.py` 重新导出了。确认无代码直接 `from .theme import get`。

---

## Phase 3: 拆分 Overlay 上帝类 (CaptureOverlay)

### Task 3.1: 提取裁剪模式 (`CropMode`)
将 `_crop_mode`, `_crop_rect`, `_crop_dragging`, `_crop_start`, `_crop_handle` 及相关 6 个方法提取到 `overlay/crop_mode.py` 中独立的类。
- Verify: CaptureOverlay 减少 ~100 行

### Task 3.2: 提取窗口检测逻辑
将 `_detected_window_rect`, `_window_snap_rect` 及 auto-detect 逻辑提取到 `overlay/window_snap.py` 中。
- Verify: CaptureOverlay 减少 ~30 行

### Task 3.3: 简化 CaptureOverlay.__init__
将 30+ 个实例变量按功能分组为 dataclass 字段（SelectionState, DrawingState, AnnotationEditState, CropState, TextEditState）。
- Verify: `__init__` 从 ~90 行降到 ~40 行

---

## Phase 4: UI 子包化

### Task 4.1: 按功能分包 `src/ui/`
```
ui/
├── settings/     # 已有
├── pin/          # pin_window.py, pin_actions.py, pin_rendering.py → 移到 pin/
├── ocr/          # ocr_dialog.py, ocr_progress_dialog.py, ocr_test_dialog.py → 移到 ocr/
├── common/       # toast.py, toggle_switch.py, title_bar.py, color_picker.py
├── tray.py       # 核心保留
└── settings_dialog.py  # 转发到 settings/
```
- Verify: 更新所有 import，运行测试

---

## Verifications

### Phase X-1: 运行现有测试
```bash
python -m pytest tests/ -v --tb=short
```
确保重构前后测试全部通过。

### Phase X-2: 手动启动验证
```bash
python main.py
```
启动应用，验证托盘图标 > 截图 > 标注 > 贴图 > 设置 核心流程正常。
