from PySide6.QtGui import QColor

from src.core.constants import (
    ARROW_SIZE_BASE,
    DEFAULT_FONT_SIZE,
    DEFAULT_LINE_WIDTH,
    HANDLE_SIZE,
    ICON_RENDER_SIZE,
    ICON_SIZE_BTN,
    ICON_SIZE_MENU,
    ICON_SIZE_SMALL,
    MIN_DRAW_THRESHOLD,
    MIN_SELECTION_SIZE,
    MOSAIC_SCALE_FACTOR,
    PRESET_COLORS,
    SHADOW_BLUR,
    TEXT_PRESET_COLORS,
    TOOLBAR_HEIGHT,
)


class TestColorConstants:
    def test_default_annotation_color(self):
        from src.core.constants import DEFAULT_ANNOTATION_COLOR

        assert isinstance(DEFAULT_ANNOTATION_COLOR, QColor)
        assert DEFAULT_ANNOTATION_COLOR.isValid()

    def test_dim_overlay_has_alpha(self):
        from src.core.constants import DIM_OVERLAY_COLOR

        assert DIM_OVERLAY_COLOR.alpha() > 0

    def test_preset_colors_count(self):
        assert len(PRESET_COLORS) == 5

    def test_preset_colors_valid_hex(self):
        import re
        hex_pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
        for color in PRESET_COLORS:
            assert hex_pattern.match(color), f"{color} is not a valid hex color"

    def test_text_preset_colors_shape(self):
        assert len(TEXT_PRESET_COLORS) == 2
        assert len(TEXT_PRESET_COLORS[0]) == 5
        assert len(TEXT_PRESET_COLORS[1]) == 5

    def test_text_preset_colors_valid_hex(self):
        import re
        hex_pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
        for group in TEXT_PRESET_COLORS:
            for color in group:
                assert hex_pattern.match(color), f"{color} is not a valid hex color"


class TestSizeConstants:
    def test_handle_size_positive(self):
        assert isinstance(HANDLE_SIZE, int) and HANDLE_SIZE > 0

    def test_min_selection_size_positive(self):
        assert MIN_SELECTION_SIZE > 0

    def test_min_draw_threshold_positive(self):
        assert MIN_DRAW_THRESHOLD > 0

    def test_toolbar_height_positive(self):
        assert TOOLBAR_HEIGHT > 0

    def test_icon_sizes_ordered(self):
        assert ICON_SIZE_SMALL < ICON_SIZE_MENU < ICON_SIZE_BTN
        assert ICON_RENDER_SIZE > ICON_SIZE_BTN

    def test_default_line_width_minimum(self):
        assert DEFAULT_LINE_WIDTH >= 1

    def test_default_font_size_minimum(self):
        assert DEFAULT_FONT_SIZE >= 10


class TestMiscConstants:
    def test_shadow_blur_positive(self):
        assert SHADOW_BLUR > 0

    def test_arrow_size_base_positive(self):
        assert ARROW_SIZE_BASE > 0

    def test_mosaic_scale_factor(self):
        assert MOSAIC_SCALE_FACTOR >= 2
