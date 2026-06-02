"""主题系统：亮色/暗色 token 定义 + ThemeManager 全局管理。

用法:
    theme = ThemeManager()
    color = theme.get("bg_primary")        # → "#FFFFFF"
    qss   = theme.stylesheet("background: $bg_primary; color: $text_primary")
    theme.set_theme("dark")
    theme.apply_to_app(qapp)               # 设置全局 QPalette
"""

import sys
from typing import Literal
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


# ─── Token Keys（供 IDE 补全 / 防 typo） ───
# 命名规则: bg_/text_/border_ + 语义
BG_PRIMARY       = "bg_primary"        # 主背景
BG_SECONDARY     = "bg_secondary"      # 次要背景（hover/alt row）
BG_TOOLBAR       = "bg_toolbar"        # 工具栏背景
BG_TOOLBAR_ALT   = "bg_toolbar_alt"    # 子菜单背景
BG_OVERLAY       = "bg_overlay"        # 覆盖层半透明遮罩
BG_INPUT         = "bg_input"          # 输入框背景
BG_MENU          = "bg_menu"           # 菜单/弹出面板背景

TEXT_PRIMARY     = "text_primary"      # 主文字
TEXT_SECONDARY   = "text_secondary"    # 次要文字（说明/提示）
TEXT_PLACEHOLDER = "text_placeholder"  # placeholder 文字
TEXT_DISABLED    = "text_disabled"     # 禁用状态文字
TEXT_ACCENT      = "text_accent"       # 强调色文字（按钮/选中）

BORDER           = "border"            # 常规边框
BORDER_LIGHT     = "border_light"      # 弱边框（分割线/分隔符）
BORDER_FOCUS     = "border_focus"      # 聚焦边框
BORDER_INPUT     = "border_input"      # 输入框边框

ACCENT           = "accent"            # 强调色（按钮选中/active tab）
ACCENT_HOVER     = "accent_hover"      # 强调色 hover
ACCENT_DISABLED  = "accent_disabled"   # 禁用强调色
HOVER_BG         = "hover_bg"          # hover 背景

COLOR_BTN_BORDER       = "color_btn_border"        # 颜色按钮边框
COLOR_BTN_BORDER_ON    = "color_btn_border_on"     # 颜色按钮选中边框
COLOR_BTN_RECENT_BORDER = "color_btn_recent_border"  # 最近颜色按钮边框

SHADOW           = "shadow"            # 常规阴影
TOOLBAR_SHADOW   = "toolbar_shadow"    # 工具栏阴影

OVERLAY_DIM      = "overlay_dim"       # 截图覆盖层遮罩色
SEL_BORDER       = "sel_border"        # 选区边框
SEL_FILL         = "sel_fill"          # 选区填充
SEL_HANDLE       = "sel_handle"        # 选区控制点
SEL_DASH         = "sel_dash"          # 选区虚线
INFO_BG          = "info_bg"           # 信息标签背景
INFO_TEXT         = "info_text"         # 信息标签文字
HOTKEY_CONFLICT  = "hotkey_conflict"   # 快捷键冲突提示色
INFO_LABEL_BG    = "info_label_bg"     # 信息标签背景
INFO_LABEL_FG    = "info_label_fg"     # 信息标签前景
INFO_ACCENT      = "info_accent"       # 信息强调色
HANDLE_FILL      = "handle_fill"       # 控制点填充
HANDLE_BORDER    = "handle_border"     # 控制点边框


# ─── Token Dictionaries ───

LIGHT_TOKENS: dict[str, str] = {
    BG_PRIMARY:       "#FFFFFF",
    BG_SECONDARY:     "#F5F5F5",
    BG_TOOLBAR:       "#FFFFFF",
    BG_TOOLBAR_ALT:   "#FFFFFF",
    BG_OVERLAY:       "rgba(0, 0, 0, 140)",
    BG_INPUT:         "#FFFFFF",
    BG_MENU:          "#FFFFFF",

    TEXT_PRIMARY:     "#333333",
    TEXT_SECONDARY:   "#666666",
    TEXT_PLACEHOLDER: "#999999",
    TEXT_DISABLED:    "#AAAAAA",
    TEXT_ACCENT:      "#FFFFFF",

    BORDER:           "#CCCCCC",
    BORDER_LIGHT:     "#DDDDDD",
    BORDER_FOCUS:     "#0078D4",
    BORDER_INPUT:     "#CCCCCC",

    ACCENT:           "#207FF0",
    ACCENT_HOVER:     "#1A6ACC",
    ACCENT_DISABLED:  "#A0C8F0",
    HOVER_BG:         "#E8E8E8",

    COLOR_BTN_BORDER:        "#CCCCCC",
    COLOR_BTN_BORDER_ON:     "#0078D4",
    COLOR_BTN_RECENT_BORDER: "#999999",

    SHADOW:           "rgba(0, 0, 0, 60)",
    TOOLBAR_SHADOW:   "rgba(0, 0, 0, 120)",

    OVERLAY_DIM:      "rgba(0, 0, 0, 140)",
    SEL_BORDER:       "rgba(0, 120, 215, 255)",
    SEL_FILL:         "rgba(0, 120, 215, 30)",
    SEL_HANDLE:       "rgba(255, 255, 255, 180)",
    SEL_DASH:         "rgba(0, 0, 0, 120)",
    INFO_BG:          "rgba(0, 0, 0, 100)",
    INFO_TEXT:        "rgba(255, 255, 255, 220)",

    HOTKEY_CONFLICT:  "#CC0000",
    INFO_LABEL_BG:    "rgba(0, 0, 0, 100)",
    INFO_LABEL_FG:    "rgba(255, 255, 255, 220)",
    INFO_ACCENT:      "rgba(30, 144, 255, 180)",
    HANDLE_FILL:      "rgba(255, 255, 255, 40)",
    HANDLE_BORDER:    "rgba(255, 255, 255, 180)",
}

DARK_TOKENS: dict[str, str] = {
    BG_PRIMARY:       "#1E1E1E",
    BG_SECONDARY:     "#252526",
    BG_TOOLBAR:       "#2D2D2D",
    BG_TOOLBAR_ALT:   "#333333",
    BG_OVERLAY:       "rgba(0, 0, 0, 180)",
    BG_INPUT:         "#3C3C3C",
    BG_MENU:          "#2D2D2D",

    TEXT_PRIMARY:     "#CCCCCC",
    TEXT_SECONDARY:   "#999999",
    TEXT_PLACEHOLDER: "#666666",
    TEXT_DISABLED:    "#555555",
    TEXT_ACCENT:      "#FFFFFF",

    BORDER:           "#555555",
    BORDER_LIGHT:     "#444444",
    BORDER_FOCUS:     "#1A8CFF",
    BORDER_INPUT:     "#555555",

    ACCENT:           "#207FF0",
    ACCENT_HOVER:     "#3399FF",
    ACCENT_DISABLED:  "#1A5A8A",
    HOVER_BG:         "#3A3A3A",

    COLOR_BTN_BORDER:        "#555555",
    COLOR_BTN_BORDER_ON:     "#1A8CFF",
    COLOR_BTN_RECENT_BORDER: "#777777",

    SHADOW:           "rgba(0, 0, 0, 100)",
    TOOLBAR_SHADOW:   "rgba(0, 0, 0, 160)",

    OVERLAY_DIM:      "rgba(0, 0, 0, 180)",
    SEL_BORDER:       "rgba(26, 140, 255, 255)",
    SEL_FILL:         "rgba(26, 140, 255, 30)",
    SEL_HANDLE:       "rgba(255, 255, 255, 180)",
    SEL_DASH:         "rgba(255, 255, 255, 120)",
    INFO_BG:          "rgba(0, 0, 0, 100)",
    INFO_TEXT:        "rgba(255, 255, 255, 220)",

    HOTKEY_CONFLICT:  "#FF4444",
    INFO_LABEL_BG:    "rgba(0, 0, 0, 120)",
    INFO_LABEL_FG:    "rgba(255, 255, 255, 220)",
    INFO_ACCENT:      "rgba(30, 144, 255, 180)",
    HANDLE_FILL:      "rgba(60, 60, 60, 40)",
    HANDLE_BORDER:    "rgba(255, 255, 255, 180)",
}

# Theme mode type
ThemeMode = Literal["light", "dark", "system"]


def _detect_system_theme() -> Literal["light", "dark"]:
    """检测操作系统当前主题（仅 Windows 实现）。"""
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if value else "dark"
        except Exception:
            return "light"
    elif sys.platform == "darwin":
        # macOS - 可通过 NSUserDefaults 检测
        try:
            import subprocess
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2
            )
            return "dark" if result.stdout.strip() == "Dark" else "light"
        except Exception:
            return "light"
    return "light"


class ThemeManager(QObject):
    """全局主题管理器（单例）。

    用法:
        theme = ThemeManager()
        theme.set_theme("dark")
        color = theme.get("bg_primary")
        qss_text = theme.stylesheet("background: $bg_primary;")
    """

    theme_changed = Signal(str)  # "light" | "dark"

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, parent: QObject | None = None) -> None:
        if hasattr(self, "_initialized"):
            return
        super().__init__(parent)
        self._initialized = True
        self._mode: ThemeMode = "light"     # 用户偏好设置值
        self._resolved: str = "light"       # 实际生效（跟随系统时=系统值）
        self._tokens: dict[str, str] = LIGHT_TOKENS.copy()

    # ─── Public API ───

    @property
    def mode(self) -> ThemeMode:
        """用户偏好的主题模式。"""
        return self._mode

    def set_mode(self, mode: ThemeMode) -> None:
        """设置用户偏好模式（light/dark/system）。"""
        self._mode = mode
        self._resolve_and_apply()

    def get(self, token: str, default: str = "") -> str:
        """获取当前主题的色值。"""
        return self._tokens.get(token, default)

    def qss(self, template: str) -> str:
        """将 QSS 模板中的 $token 替换为当前主题色值。

        例:
            qss = theme.qss("background: $bg_primary; color: $text_primary;")
            # → "background: #1E1E1E; color: #CCCCCC;"
        """
        result = template
        for token, color in self._tokens.items():
            result = result.replace(f"${token}", color)
        return result

    def stylesheet(self, template: str) -> str:
        """qss() 的别名。"""
        return self.qss(template)

    def is_dark(self) -> bool:
        return self._resolved == "dark"

    @property
    def resolved(self) -> str:
        return self._resolved

    def build_palette(self, theme: str) -> QPalette:
        """根据主题名生成 QPalette。"""
        palette = QPalette()
        if theme == "light":
            palette.setColor(QPalette.Window, QColor("#F0F0F0"))
            palette.setColor(QPalette.WindowText, QColor("#333333"))
            palette.setColor(QPalette.Base, QColor("#FFFFFF"))
            palette.setColor(QPalette.AlternateBase, QColor("#F5F5F5"))
            palette.setColor(QPalette.Text, QColor("#333333"))
            palette.setColor(QPalette.Button, QColor("#F0F0F0"))
            palette.setColor(QPalette.ButtonText, QColor("#333333"))
            palette.setColor(QPalette.BrightText, QColor("#FFFFFF"))
            palette.setColor(QPalette.Highlight, QColor("#207FF0"))
            palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
            palette.setColor(QPalette.ToolTipBase, QColor("#FFFFFF"))
            palette.setColor(QPalette.ToolTipText, QColor("#333333"))
            palette.setColor(QPalette.PlaceholderText, QColor("#999999"))
            palette.setColor(QPalette.Light, QColor("#E0E0E0"))
            palette.setColor(QPalette.Midlight, QColor("#D0D0D0"))
            palette.setColor(QPalette.Mid, QColor("#CCCCCC"))
            palette.setColor(QPalette.Dark, QColor("#999999"))
            palette.setColor(QPalette.Shadow, QColor("rgba(0,0,0,60)"))
            palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#AAAAAA"))
            palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#AAAAAA"))
        else:
            palette.setColor(QPalette.Window, QColor("#2D2D2D"))
            palette.setColor(QPalette.WindowText, QColor("#CCCCCC"))
            palette.setColor(QPalette.Base, QColor("#1E1E1E"))
            palette.setColor(QPalette.AlternateBase, QColor("#252526"))
            palette.setColor(QPalette.Text, QColor("#CCCCCC"))
            palette.setColor(QPalette.Button, QColor("#3C3C3C"))
            palette.setColor(QPalette.ButtonText, QColor("#CCCCCC"))
            palette.setColor(QPalette.BrightText, QColor("#FFFFFF"))
            palette.setColor(QPalette.Highlight, QColor("#207FF0"))
            palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
            palette.setColor(QPalette.ToolTipBase, QColor("#333333"))
            palette.setColor(QPalette.ToolTipText, QColor("#CCCCCC"))
            palette.setColor(QPalette.PlaceholderText, QColor("#666666"))
            palette.setColor(QPalette.Light, QColor("#3C3C3C"))
            palette.setColor(QPalette.Midlight, QColor("#444444"))
            palette.setColor(QPalette.Mid, QColor("#555555"))
            palette.setColor(QPalette.Dark, QColor("#666666"))
            palette.setColor(QPalette.Shadow, QColor("rgba(0,0,0,100)"))
            palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#555555"))
            palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#555555"))
        return palette

    def apply_to_app(self, app: QApplication) -> None:
        """将当前主题的 QPalette 应用到全局 QApplication。"""
        palette = self.build_palette(self._resolved)
        app.setPalette(palette)
        # 注意：QPalette 不会自动触发所有 widget 重绘
        # setStyleSheet("") 会触发全局样式刷新
        app.setStyleSheet(app.styleSheet() or "")

    def apply_to_widget(self, widget, theme: str | None = None) -> None:
        """为单个 widget 设置主题 QPalette。"""
        t = theme or self._resolved
        palette = self.build_palette(t)
        widget.setPalette(palette)

    # ─── Internal ───

    def _resolve_and_apply(self) -> None:
        """根据 mode 解析实际主题并应用。"""
        if self._mode == "system":
            self._resolved = _detect_system_theme()
        else:
            self._resolved = self._mode
        self._tokens = (DARK_TOKENS if self._resolved == "dark" else LIGHT_TOKENS).copy()
        self.theme_changed.emit(self._resolved)


# 模块级快捷访问
theme = ThemeManager()
get = theme.get
qss = theme.qss
