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

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .logger import setup_logger

logger = setup_logger("theme")


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
    BG_TOOLBAR:       "#FFFFFFD7",   # alpha=215
    BG_TOOLBAR_ALT:   "#FFFFFFE6",   # alpha=230
    BG_OVERLAY:       "#0000008C",   # alpha=140
    BG_INPUT:         "#FFFFFF",
    BG_MENU:          "#FFFFFF",

    TEXT_PRIMARY:     "#333333",
    TEXT_SECONDARY:   "#666666",
    TEXT_PLACEHOLDER: "#999999",
    TEXT_DISABLED:    "#AAAAAA",
    TEXT_ACCENT:      "#FFFFFF",

    BORDER:           "#CCCCCC",
    BORDER_LIGHT:     "#DDDDDD",
    BORDER_FOCUS:     "#00897B",     # 深青色
    BORDER_INPUT:     "#CCCCCC",

    ACCENT:           "#00897B",     # 深青（Material Teal 700）
    ACCENT_HOVER:     "#00695C",     # 更深青（悬停）
    ACCENT_DISABLED:  "#4DB6AC",     # 浅青（禁用）
    HOVER_BG:         "#E8E8E8",

    COLOR_BTN_BORDER:        "#CCCCCC",
    COLOR_BTN_BORDER_ON:     "#00897B",     # 深青色
    COLOR_BTN_RECENT_BORDER: "#999999",

    SHADOW:           "#0000003C",   # alpha=60
    TOOLBAR_SHADOW:   "#00000078",   # alpha=120

    OVERLAY_DIM:      "#0000008C",   # alpha=140 — 截图遮罩
    SEL_BORDER:       "#00897B",     # 深青选区边框
    SEL_FILL:         "#00897B1E",   # alpha=30
    SEL_HANDLE:       "#FFFFFFB4",   # alpha=180
    SEL_DASH:         "#00000078",   # alpha=120
    INFO_BG:          "#00000064",   # alpha=100
    INFO_TEXT:        "#FFFFFFDC",   # alpha=220

    HOTKEY_CONFLICT:  "#CC0000",
    INFO_LABEL_BG:    "#00000064",   # alpha=100
    INFO_LABEL_FG:    "#FFFFFFDC",   # alpha=220
    INFO_ACCENT:      "#00897BB4",   # alpha=180 深青
    HANDLE_FILL:      "#FFFFFF28",   # alpha=40
    HANDLE_BORDER:    "#FFFFFFB4",   # alpha=180
}

DARK_TOKENS: dict[str, str] = {
    BG_PRIMARY:       "#1E1E1E",
    BG_SECONDARY:     "#252526",
    BG_TOOLBAR:       "#2D2D2DD7",  # alpha=215
    BG_TOOLBAR_ALT:   "#333333E6",  # alpha=230
    BG_OVERLAY:       "#000000B4",  # alpha=180
    BG_INPUT:         "#3C3C3C",
    BG_MENU:          "#2D2D2D",

    TEXT_PRIMARY:     "#CCCCCC",
    TEXT_SECONDARY:   "#999999",
    TEXT_PLACEHOLDER: "#666666",
    TEXT_DISABLED:    "#555555",
    TEXT_ACCENT:      "#FFFFFF",

    BORDER:           "#555555",
    BORDER_LIGHT:     "#444444",
    BORDER_FOCUS:     "#4DB6AC",     # 亮青（暗色模式更亮）
    BORDER_INPUT:     "#555555",

    ACCENT:           "#4DB6AC",     # 亮青（主色）
    ACCENT_HOVER:     "#26A69A",     # 浓青（悬停）
    ACCENT_DISABLED:  "#80CBC4",     # 淡青（禁用）
    HOVER_BG:         "#3A3A3A",

    COLOR_BTN_BORDER:        "#555555",
    COLOR_BTN_BORDER_ON:     "#4DB6AC",     # 亮青
    COLOR_BTN_RECENT_BORDER: "#777777",

    SHADOW:           "#00000064",   # alpha=100
    TOOLBAR_SHADOW:   "#000000A0",   # alpha=160

    OVERLAY_DIM:      "#000000B4",   # alpha=180
    SEL_BORDER:       "#4DB6AC",     # 亮青选区边框
    SEL_FILL:         "#4DB6AC1E",   # alpha=30
    SEL_HANDLE:       "#FFFFFFB4",   # alpha=180
    SEL_DASH:         "#FFFFFF78",   # alpha=120
    INFO_BG:          "#00000064",   # alpha=100
    INFO_TEXT:        "#FFFFFFDC",   # alpha=220

    HOTKEY_CONFLICT:  "#FF4444",
    INFO_LABEL_BG:    "#00000078",   # alpha=120
    INFO_LABEL_FG:    "#FFFFFFDC",   # alpha=220
    INFO_ACCENT:      "#4DB6ACB4",   # alpha=180 亮青
    HANDLE_FILL:      "#3C3C3C28",   # alpha=40
    HANDLE_BORDER:    "#FFFFFFB4",   # alpha=180
}

# Theme mode type
ThemeMode = Literal["light", "dark", "system"]


def _derive_accent_colors(base_color: str, is_dark: bool) -> dict[str, str]:
    """根据基础主题色生成衍生色（hover、disabled、边框等）。

    Args:
        base_color: 基础颜色 hex 字符串，如 "#FF5722"
        is_dark: 是否为暗色模式

    Returns:
        包含所有 accent 相关 token 的字典
    """
    from PySide6.QtGui import QColor
    c = QColor(base_color)
    h, s, lightness, _ = c.getHslF()

    if is_dark:
        # 暗色模式：hover 更亮，disabled 更淡
        hover_l = min(lightness + 0.1, 0.9)
        disabled_s = s * 0.5
        disabled_l = min(lightness + 0.2, 0.8)
    else:
        # 亮色模式：hover 更暗
        hover_l = max(lightness - 0.1, 0.1)
        disabled_s = s * 0.5
        disabled_l = min(lightness + 0.15, 0.7)

    hover = QColor.fromHslF(h, s, hover_l)
    disabled = QColor.fromHslF(h, disabled_s, disabled_l)

    return {
        ACCENT: base_color,
        ACCENT_HOVER: hover.name(),
        ACCENT_DISABLED: disabled.name(),
        BORDER_FOCUS: base_color,
        COLOR_BTN_BORDER_ON: base_color,
        SEL_BORDER: base_color,
        SEL_FILL: base_color + "1E",  # alpha=30
        INFO_ACCENT: base_color + "B4",  # alpha=180
    }


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
        self._custom_accent: str = ""       # 自定义主题色
        self._system_timer: QTimer | None = None  # 系统主题轮询定时器（延迟创建）

    # ─── Public API ───

    @property
    def mode(self) -> ThemeMode:
        """用户偏好的主题模式。"""
        return self._mode

    def set_mode(self, mode: ThemeMode) -> None:
        """设置用户偏好模式（light/dark/system）。"""
        self._mode = mode
        self._resolve_and_apply()
        # 管理系统主题轮询定时器（仅 mode=="system" 时运行）
        if mode == "system":
            if self._system_timer is None:
                self._system_timer = QTimer(self)
                self._system_timer.setInterval(2000)
                self._system_timer.timeout.connect(self._check_system_theme)
            if not self._system_timer.isActive():
                logger.info(
                    "Started system theme polling "
                    f"(interval={self._system_timer.interval()}ms, detected={self._resolved})"
                )
                self._system_timer.start()
        else:
            if self._system_timer is not None and self._system_timer.isActive():
                logger.info("Stopped system theme polling")
                self._system_timer.stop()

    def get(self, token: str, default: str = "") -> str:
        """获取当前主题的色值。"""
        return self._tokens.get(token, default)

    def qss(self, template: str) -> str:
        """将 QSS 模板中的 $token 替换为当前主题色值。

        自动将 #RRGGBBAA hex 格式转换为 rgba(r,g,b,a) 格式，
        因为 QSS 不支持 8 位 hex 颜色。

        例:
            qss = theme.qss("background: $bg_primary; color: $text_primary;")
            # → "background: rgba(255,255,255,215); color: #333333;"
        """
        result = template
        # Sort by key length descending so longer keys (e.g. "border_light")
        # are replaced before shorter prefix keys (e.g. "border").
        for token, color in sorted(self._tokens.items(), key=lambda kv: len(kv[0]), reverse=True):
            # QSS 不支持 #RRGGBBAA，转换为 rgba(r,g,b,a)
            if color.startswith("#") and len(color) == 9:
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                a = int(color[7:9], 16)
                color_str = f"rgba({r},{g},{b},{a})"
            else:
                color_str = color
            result = result.replace(f"${token}", color_str)
        return result

    def stylesheet(self, template: str) -> str:
        """qss() 的别名。"""
        return self.qss(template)

    def is_dark(self) -> bool:
        return self._resolved == "dark"

    @property
    def resolved(self) -> str:
        return self._resolved

    @property
    def accent_color(self) -> str:
        """获取当前主题色（自定义或默认）"""
        return self._custom_accent or self.get(ACCENT)

    def set_accent_color(self, color: str) -> None:
        """设置自定义主题色。

        Args:
            color: 颜色 hex 字符串，如 "#FF5722"；空字符串恢复默认
        """
        self._custom_accent = color
        self._resolve_and_apply()

    def build_palette(self, theme: str) -> QPalette:
        """根据主题名生成 QPalette。"""
        palette = QPalette()
        # 使用自定义主题色或默认色
        if self._custom_accent:
            accent = self._custom_accent
        else:
            accent = "#00897B" if theme == "light" else "#4DB6AC"

        if theme == "light":
            palette.setColor(QPalette.Window, QColor("#F0F0F0"))
            palette.setColor(QPalette.WindowText, QColor("#333333"))
            palette.setColor(QPalette.Base, QColor("#FFFFFF"))
            palette.setColor(QPalette.AlternateBase, QColor("#F5F5F5"))
            palette.setColor(QPalette.Text, QColor("#333333"))
            palette.setColor(QPalette.Button, QColor("#CCCCCC"))
            palette.setColor(QPalette.ButtonText, QColor("#333333"))
            palette.setColor(QPalette.BrightText, QColor("#FFFFFF"))
            palette.setColor(QPalette.Highlight, QColor(accent))
            palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
            palette.setColor(QPalette.ToolTipBase, QColor("#FFFFFF"))
            palette.setColor(QPalette.ToolTipText, QColor("#333333"))
            palette.setColor(QPalette.PlaceholderText, QColor("#999999"))
            palette.setColor(QPalette.Light, QColor("#E0E0E0"))
            palette.setColor(QPalette.Midlight, QColor("#D0D0D0"))
            palette.setColor(QPalette.Mid, QColor("#CCCCCC"))
            palette.setColor(QPalette.Dark, QColor("#999999"))
            palette.setColor(QPalette.Shadow, QColor("#0000003C"))
            palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#AAAAAA"))
            palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#AAAAAA"))
        else:
            palette.setColor(QPalette.Window, QColor("#2D2D2D"))
            palette.setColor(QPalette.WindowText, QColor("#CCCCCC"))
            palette.setColor(QPalette.Base, QColor("#1E1E1E"))
            palette.setColor(QPalette.AlternateBase, QColor("#252526"))
            palette.setColor(QPalette.Text, QColor("#CCCCCC"))
            palette.setColor(QPalette.Button, QColor("#5A5A5A"))
            palette.setColor(QPalette.ButtonText, QColor("#CCCCCC"))
            palette.setColor(QPalette.BrightText, QColor("#FFFFFF"))
            palette.setColor(QPalette.Highlight, QColor(accent))
            palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
            palette.setColor(QPalette.ToolTipBase, QColor("#333333"))
            palette.setColor(QPalette.ToolTipText, QColor("#CCCCCC"))
            palette.setColor(QPalette.PlaceholderText, QColor("#666666"))
            palette.setColor(QPalette.Light, QColor("#3C3C3C"))
            palette.setColor(QPalette.Midlight, QColor("#444444"))
            palette.setColor(QPalette.Mid, QColor("#555555"))
            palette.setColor(QPalette.Dark, QColor("#666666"))
            palette.setColor(QPalette.Shadow, QColor("#00000064"))
            palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#555555"))
            palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#555555"))
        return palette

    def apply_to_app(self, app: QApplication) -> None:
        """将当前主题的 QPalette 应用到全局 QApplication。"""
        palette = self.build_palette(self._resolved)
        app.setPalette(palette)
        # 重要：不要在此处调用 app.setStyleSheet("") 或 app.setStyle(app.style())，
        # 这会破坏 WA_TranslucentBackground 窗口的渲染（已知 Qt6 bug）。
        # setPalette 本身已经会触发 widget 重绘。

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

        # 应用自定义主题色
        if self._custom_accent:
            derived = _derive_accent_colors(self._custom_accent, self._resolved == "dark")
            self._tokens.update(derived)

        self.theme_changed.emit(self._resolved)

    def _check_system_theme(self) -> None:
        """轮询检测系统主题是否变化（仅 mode=="system" 时由定时器触发）。"""
        detected = _detect_system_theme()
        if detected != self._resolved:
            logger.info(f"System theme changed: {self._resolved} -> {detected}")
            self._resolve_and_apply()
            app = QApplication.instance()
            if app:
                logger.info("Applying theme palette to QApplication")
                self.apply_to_app(app)
        else:
            logger.debug(f"System theme check: still {detected} (no change)")


# 模块级快捷访问
theme = ThemeManager()
get = theme.get
qss = theme.qss


def apply_dark_title_bar(window, dark: bool = True) -> None:
    """Set dark title bar color on supported platforms.

    Windows 10 20H1+ / Windows 11 — uses DWM immersive dark mode.
    macOS / Linux — no-op (system handles it automatically).
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        dwmapi = ctypes.windll.dwmapi
        user32 = ctypes.windll.user32

        hwnd = wintypes.HWND(int(window.winId()))
        if not hwnd:
            logger.debug("apply_dark_title_bar: invalid window handle")
            return
        value = ctypes.c_int(1 if dark else 0)
        # 兼容 Windows 10 20H1+ (20) 和更早版本 (19)
        for attr_id in (20, 19):
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                wintypes.DWORD(attr_id),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        # 强制 DWM 重绘框架
        SWP_FRAMECHANGED = 0x0020
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                            SWP_FRAMECHANGED | 0x0002 | 0x0001 | 0x0004)
        # 通知 DWM 重绘
        WM_DWMCOMPOSITIONCHANGED = 0x031E
        user32.SendMessageW(hwnd, WM_DWMCOMPOSITIONCHANGED, 0, 0)
        logger.debug(f"apply_dark_title_bar: dark={dark}")
    except Exception as e:
        logger.debug(f"apply_dark_title_bar failed: {e}")
