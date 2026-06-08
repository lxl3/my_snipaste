"""macOS Big Sur 风格的毛玻璃效果 - 通用绘制函数

提供统一的玻璃态视觉效果，可用于各种 UI 组件：
- Toast 通知
- 悬浮提示
- 对话框背景
- 工具栏
等等。
"""

from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient
from PySide6.QtCore import Qt, QRectF


def draw_glass_morphism(
    painter: QPainter,
    rect: QRectF,
    radius: float = 12,
    is_dark: bool = False,
    draw_shadow: bool = True,
    bg_opacity: tuple[int, int, int] | None = None,
    shadow_intensity: float = 1.0,
) -> None:
    """绘制 macOS Big Sur 风格的毛玻璃效果

    视觉层次（从底到顶）：
    1. 外层投影（可选，多层叠加）
    2. 主背景渐变（半透明白色）
    3. 顶部高光带（强烈的边缘高光）
    4. 外边框（柔和的半透明边框）
    5. 内边框（内侧细亮线）

    Args:
        painter: QPainter 对象
        rect: 绘制区域（QRectF）
        radius: 圆角半径，默认 12（Big Sur 风格）
        is_dark: 是否为暗色模式
        draw_shadow: 是否绘制外层投影，默认 True
        bg_opacity: 背景透明度 (top, mid, bottom)，None 使用默认值
                    暗色模式默认: (200, 185, 170)
                    亮色模式默认: (235, 225, 215)
        shadow_intensity: 投影强度系数，默认 1.0，范围 0.0-2.0

    Example:
        from ..core.glass_effect import draw_glass_morphism
        from ..core.theme import theme

        painter = QPainter(self)
        rect = QRectF(10, 10, 200, 60)
        draw_glass_morphism(painter, rect, is_dark=theme.is_dark())
    """
    bx, by, bw, bh = rect.x(), rect.y(), rect.width(), rect.height()

    # 1. 外层投影 — 在 card 外围扩散的平滑阴影（模拟光源在上方）
    if draw_shadow:
        shadow_layers = 6
        spread = 3               # 均匀扩展宽度（px）
        bottom_spread = 4        # 底部额外扩展（光源在上方）
        # 亮色模式阴影更淡，避免黑边
        base_alpha = 12 if not is_dark else 18

        # 从外（alpha 低）到内（alpha 高）逐层绘制，多层叠加实现平滑衰减
        for i in range(shadow_layers):
            t = i / shadow_layers                       # 0→1
            alpha = int(base_alpha * shadow_intensity * t)
            if alpha <= 0:
                continue

            # 逐层缩小：外层离 card 远 → 内层贴近 card
            expand = spread * (1 - t)                    # 向外扩散量
            bottom_expand = bottom_spread * (1 - t)      # 底部额外扩散

            shadow_rect = QRectF(
                bx - expand,
                by - expand,
                bw + expand * 2,
                bh + expand * 2 + bottom_expand
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(shadow_rect, radius, radius)

    # 2. 主背景：半透明渐变（根据主题模式调整颜色）
    if bg_opacity is None:
        if is_dark:
            # 暗色模式：高透明度（玻璃质感）
            bg_opacity = (120, 110, 100)
        else:
            # 亮色模式：更不透明以遮盖阴影
            bg_opacity = (230, 220, 210)

    gradient = QLinearGradient(bx, by, bx, by + bh)
    if is_dark:
        # 暗色模式：深色半透明背景
        gradient.setColorAt(0, QColor(50, 50, 50, bg_opacity[0]))     # 顶部更亮
        gradient.setColorAt(0.5, QColor(45, 45, 45, bg_opacity[1]))   # 中部
        gradient.setColorAt(1, QColor(40, 40, 40, bg_opacity[2]))     # 底部稍暗
    else:
        # 亮色模式：白色半透明背景
        gradient.setColorAt(0, QColor(255, 255, 255, bg_opacity[0]))
        gradient.setColorAt(0.5, QColor(250, 250, 250, bg_opacity[1]))
        gradient.setColorAt(1, QColor(245, 245, 245, bg_opacity[2]))

    painter.setBrush(gradient)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(rect, radius, radius)

    # 3. 顶部强烈高光（Big Sur 标志性的边缘高光）
    top_highlight = QLinearGradient(bx, by, bx, by + 3)
    if is_dark:
        # 暗色模式：较柔和的高光
        top_highlight.setColorAt(0, QColor(255, 255, 255, 100))
        top_highlight.setColorAt(1, QColor(255, 255, 255, 0))
    else:
        # 亮色模式：强烈高光
        top_highlight.setColorAt(0, QColor(255, 255, 255, 180))
        top_highlight.setColorAt(1, QColor(255, 255, 255, 0))

    painter.setBrush(top_highlight)
    painter.setPen(Qt.NoPen)
    # 只绘制顶部 3px 的高光带
    painter.setClipRect(int(bx), int(by), int(bw), 3)
    painter.drawRoundedRect(rect, radius, radius)
    painter.setClipping(False)

    # 4. 外边框：柔和的半透明边框
    if is_dark:
        border_color = QColor(255, 255, 255, 80)  # 暗色模式：亮边框
    else:
        border_color = QColor(220, 220, 220, 80)  # 亮色模式：浅灰边框

    painter.setPen(QPen(border_color, 1))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

    # 5. 内边框：内侧的细亮线（增强玻璃质感）
    if is_dark:
        inner_border = QColor(255, 255, 255, 40)  # 暗色模式：柔和内亮线
    else:
        inner_border = QColor(255, 255, 255, 60)  # 亮色模式：白色内亮线

    painter.setPen(QPen(inner_border, 0.5))
    painter.drawRoundedRect(rect.adjusted(1.5, 1.5, -1.5, -1.5), radius - 1, radius - 1)


def draw_glass_text(
    painter: QPainter,
    x: int,
    y: int,
    text: str,
    is_dark: bool = False,
    glow_enabled: bool = True,
) -> None:
    """在毛玻璃背景上绘制文字（根据主题调整颜色）

    根据主题模式调整文字和光晕颜色，确保清晰可读。

    Args:
        painter: QPainter 对象
        x: 文字 x 坐标
        y: 文字 y 坐标（baseline）
        text: 要绘制的文字
        is_dark: 是否为暗色模式
        glow_enabled: 是否启用光晕效果，默认 True
    """
    # 根据主题调整文字和光晕颜色
    if is_dark:
        # 暗色模式：浅色文字 + 深色阴影（在深色背景上）
        if glow_enabled:
            painter.setPen(QColor(0, 0, 0, 180))  # 深色阴影
            for offset in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                painter.drawText(x + offset[0], y + offset[1], text)
        text_color = QColor(240, 240, 240, 255)  # 浅色文字
    else:
        # 亮色模式：深色文字 + 白色光晕（在白色背景上）
        if glow_enabled:
            painter.setPen(QColor(255, 255, 255, 200))  # 白色光晕
            for offset in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                painter.drawText(x + offset[0], y + offset[1], text)
        text_color = QColor(40, 40, 40, 255)  # 深色文字

    painter.setPen(text_color)
    painter.drawText(x, y, text)
