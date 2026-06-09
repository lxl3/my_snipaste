"""工具栏声明式配置

每个工具的配置包括：
- id: 工具唯一标识
- icon: 图标名称
- tooltip: 提示文字
- tools: 子工具列表（可选）
- options: 选项控件配置
"""

from ...core.constants import PRESET_COLORS, TEXT_PRESET_COLORS


# 工具栏配置
TOOLBAR_CONFIG = [
    {
        "id": "shape",
        "icon": "rectangle",
        "tooltip": "Shape (Rectangle / Ellipse)",
        "tools": [
            {"id": "rect", "icon": "rectangle", "tooltip": "Rectangle"},
            {"id": "ellipse", "icon": "ellipse", "tooltip": "Ellipse"},
        ],
        "default_tool": "rect",
        "options": [
            {"type": "color_picker"},
            {"type": "color_buttons", "colors": PRESET_COLORS, "target": "shape"},
        ],
    },
    {
        "id": "arrow",
        "icon": "arrow",
        "tooltip": "Arrow (Arrow / Line)",
        "tools": [
            {
                "id": "arrow",
                "type": "style_combo",
                "width": 85,
                "styles": [
                    ("solid", "arrow_solid", "Solid"),
                    ("hollow", "arrow_hollow", "Hollow"),
                    ("solid_tail", "arrow_solid_tail", "Solid Tail"),
                    ("hollow_tail", "arrow_hollow_tail", "Hollow Tail"),
                ],
            },
            {"id": "line", "icon": "line", "tooltip": "Line"},
        ],
        "default_tool": "arrow",
        "options": [
            {"type": "color_picker"},
            {"type": "color_buttons", "colors": PRESET_COLORS, "target": "arrow"},
        ],
    },
    {
        "id": "pen",
        "icon": "pen",
        "tooltip": "Pen",
        "tools": [
            {"id": "freehand", "icon": "pen", "tooltip": "Pen", "implicit": True},
        ],
        "default_tool": "freehand",
        "options": [
            {"type": "color_buttons", "colors": PRESET_COLORS, "target": "pen"},
            {"type": "separator"},
            {"type": "width_spinbox", "range": (1, 20), "width": 50},
        ],
    },
    {
        "id": "highlighter",
        "icon": "highlighter",
        "tooltip": "Highlighter",
        "single_tool": "highlighter",
    },
    {
        "id": "mosaic",
        "icon": "mosaic",
        "tooltip": "Mosaic / Blur",
        "tools": [
            {"id": "mosaic", "icon": "mosaic", "tooltip": "Mosaic"},
            {"id": "blur", "icon": "blur", "tooltip": "Blur"},
        ],
        "default_tool": "mosaic",
        "options": [
            {"type": "separator"},
            {
                "type": "spinbox_group",
                "id": "blur",
                "label": "Blur:",
                "range": (1, 50),
                "width": 45,
                "property": "blur_radius",
                "visible_when": "blur",
            },
            {
                "type": "spinbox_group",
                "id": "mosaic",
                "label": "Mosaic:",
                "range": (2, 30),
                "width": 45,
                "property": "mosaic_scale",
                "visible_when": "mosaic",
            },
        ],
    },
    {
        "id": "magnifier",
        "icon": "magnifier",
        "tooltip": "Magnifier",
        "single_tool": "magnifier",
    },
    {
        "id": "text",
        "icon": "text",
        "tooltip": "Text / Number Marker",
        "tools": [
            {"id": "text", "icon": "text", "tooltip": "Text"},
            {"id": "number_marker", "icon": "number_marker", "tooltip": "Number Marker"},
        ],
        "default_tool": "text",
        "options": [
            {"type": "font_combo", "width": 120},
            {"type": "font_size_spinbox", "range": (8, 72), "width": 50},
            {"type": "bold_button"},
            {"type": "italic_button"},
            {"type": "separator"},
            {"type": "color_buttons", "colors": TEXT_PRESET_COLORS, "target": "text"},
        ],
    },
    {
        "id": "eraser",
        "icon": "eraser",
        "tooltip": "Eraser (Click annotation to delete)",
        "single_tool": "eraser",
    },
    {
        "id": "ocr",
        "icon": "OCR",
        "tooltip": "Text Recognition",
        "action": "ocr",
    },
]

# 操作按钮配置
ACTION_BUTTONS_CONFIG = [
    {"id": "undo", "icon": "undo", "tooltip": "Undo", "action": "undo", "stateful": True},
    {"id": "redo", "icon": "redo", "tooltip": "Redo", "action": "redo", "stateful": True},
    {"type": "separator"},
    {"id": "crop", "icon": "crop", "tooltip": "Crop to selection", "action": "confirm"},
    {"id": "pin", "icon": "pin", "tooltip": "Pin", "action": "pin"},
    {"id": "copy", "icon": "copy", "tooltip": "Copy", "action": "copy"},
    {"id": "save", "icon": "save", "tooltip": "Save", "action": "save"},
    {"id": "close", "icon": "close", "tooltip": "Cancel", "action": "cancel"},
]
