"""应用上下文 - 依赖注入容器

提供统一的依赖注入接口，减少全局函数调用，提高可测试性。

使用方式:
    # 生产环境
    ctx = AppContext.create()

    # 测试环境
    ctx = AppContext.create_mock()

    # 组件中使用
    class MyComponent:
        def __init__(self, ctx: AppContext):
            self.ctx = ctx
            # 使用 self.ctx.settings 代替 get_settings()
            # 使用 self.ctx.theme 代替全局 theme
"""
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .screenshot_history import ScreenshotHistory
    from .settings import AppSettings
    from .theme import ThemeManager


class I18nProvider:
    """国际化翻译提供者

    包装 i18n._() 函数，通过依赖注入可替换。
    """

    def __init__(self, translate_fn: Callable[[str], str] | None = None):
        self._translate_fn = translate_fn

    def t(self, text: str) -> str:
        if self._translate_fn:
            return self._translate_fn(text)
        from .i18n import _
        return _(text)

    def translate(self, text: str) -> str:
        return self.t(text)

    def __call__(self, text: str) -> str:
        """支持直接调用: ctx.i18n("key")"""
        return self.t(text)


@dataclass
class AppContext:
    """应用上下文，包含所有核心依赖

    Attributes:
        settings: 应用设置
        theme: 主题管理器
        i18n: 国际化翻译
        history: 截图历史管理器
    """
    settings: "AppSettings"
    theme: "ThemeManager"
    i18n: "I18nProvider | None" = None
    history: "ScreenshotHistory | None" = None

    def __post_init__(self):
        if self.i18n is None:
            self.i18n = I18nProvider()

    @classmethod
    def create(cls) -> "AppContext":
        """创建生产环境的上下文"""
        from .screenshot_history import ScreenshotHistory
        from .settings import get_settings
        from .theme_pkg import theme as _t

        return cls(
            settings=get_settings(),
            theme=_t,
            history=ScreenshotHistory(),
        )

    @classmethod
    def create_minimal(cls) -> "AppContext":
        """创建最小上下文（不初始化 history）"""
        from .settings import get_settings
        from .theme_pkg import theme as _t

        return cls(
            settings=get_settings(),
            theme=_t,
            history=None,
        )

    @classmethod
    def create_mock(
        cls,
        settings: "AppSettings | None" = None,
        theme: "ThemeManager | None" = None,
        i18n: "I18nProvider | None" = None,
        history: "ScreenshotHistory | None" = None,
    ) -> "AppContext":
        """创建测试用的模拟上下文

        Args:
            settings: 自定义设置实例，None 则使用默认值
            theme: 自定义主题实例，None 则使用默认
            i18n: 自定义翻译实例，None 则使用默认
            history: 自定义历史实例，None 则不初始化
        """
        from .settings import AppSettings
        from .theme_pkg import theme as _t

        return cls(
            settings=settings or AppSettings(),
            theme=theme or _t,
            i18n=i18n,
            history=history,
        )

    def get_setting(self, key: str, default=None):
        """获取设置值的便捷方法"""
        return getattr(self.settings, key, default)


# 全局上下文实例（延迟初始化）
_global_context: AppContext | None = None


def get_context() -> AppContext:
    """获取全局上下文实例

    首次调用时自动创建最小上下文。
    如需完整上下文，请调用 init_context()。
    """
    global _global_context
    if _global_context is None:
        _global_context = AppContext.create_minimal()
    return _global_context


def init_context(ctx: AppContext | None = None) -> AppContext:
    """初始化全局上下文

    Args:
        ctx: 自定义上下文，None 则创建生产环境上下文
    """
    global _global_context
    _global_context = ctx or AppContext.create()
    return _global_context


def reset_context() -> None:
    """重置全局上下文（主要用于测试）"""
    global _global_context
    _global_context = None
