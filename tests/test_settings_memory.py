from src.core.settings import AppSettings


class TestRecentColorsDefaults:
    def test_recent_colors_default(self):
        """测试最近颜色默认为空列表"""
        settings = AppSettings()
        assert settings.recent_colors == []

    def test_max_recent_colors_default(self):
        """测试最近颜色最大数量默认为5"""
        settings = AppSettings()
        assert settings.max_recent_colors == 5


class TestAddRecentColor:
    def test_add_recent_color(self, temp_settings_dir):
        """测试添加最近颜色"""
        settings = AppSettings()
        settings.add_recent_color("#ff0000")
        assert "#ff0000" in settings.recent_colors
        assert settings.recent_colors[0] == "#ff0000"

    def test_add_multiple_colors(self, temp_settings_dir):
        """测试添加多个颜色"""
        settings = AppSettings()
        settings.add_recent_color("#ff0000")
        settings.add_recent_color("#00ff00")
        settings.add_recent_color("#0000ff")
        assert len(settings.recent_colors) == 3
        assert settings.recent_colors == ["#0000ff", "#00ff00", "#ff0000"]

    def test_recent_colors_max_limit(self, temp_settings_dir):
        """测试最近颜色最多5个"""
        settings = AppSettings()
        for i in range(10):
            settings.add_recent_color(f"#00000{i}")
        assert len(settings.recent_colors) <= 5

    def test_recent_colors_max_limit_exact(self, temp_settings_dir):
        """测试添加10个颜色后只保留最近5个"""
        settings = AppSettings()
        for i in range(10):
            settings.add_recent_color(f"#00000{i}")
        assert len(settings.recent_colors) == 5
        # 应该保留最后添加的5个（降序）
        assert settings.recent_colors[0] == "#000009"
        assert settings.recent_colors[4] == "#000005"

    def test_duplicate_color_moves_to_front(self, temp_settings_dir):
        """测试重复添加颜色会移到最前面"""
        settings = AppSettings()
        settings.add_recent_color("#ff0000")
        settings.add_recent_color("#00ff00")
        settings.add_recent_color("#0000ff")
        assert settings.recent_colors == ["#0000ff", "#00ff00", "#ff0000"]

        # 再次添加 #00ff00，应该移到最前面
        settings.add_recent_color("#00ff00")
        assert settings.recent_colors == ["#00ff00", "#0000ff", "#ff0000"]
        assert len(settings.recent_colors) == 3

    def test_add_recent_color_saves(self, temp_settings_dir):
        """测试添加颜色会自动保存"""
        settings = AppSettings()
        settings.add_recent_color("#ff0000")

        # 重新加载设置，验证已保存
        loaded = AppSettings.reload()
        assert "#ff0000" in loaded.recent_colors


class TestToolSettingsDefaults:
    def test_tool_settings_default(self):
        """测试工具设置默认为空字典"""
        settings = AppSettings()
        assert settings.tool_settings == {}

    def test_last_tool_default(self):
        """测试最后使用工具默认为select"""
        settings = AppSettings()
        assert settings.last_tool == "select"


class TestSaveToolSettings:
    def test_save_tool_settings(self, temp_settings_dir):
        """测试保存工具设置"""
        settings = AppSettings()
        settings.save_tool_settings("rect", {"color": "#ff0000", "width": 3})
        tool_settings = settings.get_tool_settings("rect")
        assert tool_settings["color"] == "#ff0000"
        assert tool_settings["width"] == 3

    def test_get_tool_settings_nonexistent(self, temp_settings_dir):
        """测试获取不存在的工具设置返回空字典"""
        settings = AppSettings()
        tool_settings = settings.get_tool_settings("nonexistent")
        assert tool_settings == {}

    def test_save_multiple_tool_settings(self, temp_settings_dir):
        """测试保存多个工具的设置"""
        settings = AppSettings()
        settings.save_tool_settings("rect", {"color": "#ff0000", "width": 3})
        settings.save_tool_settings("ellipse", {"color": "#00ff00", "width": 5})
        settings.save_tool_settings("arrow", {"color": "#0000ff", "width": 2})

        assert len(settings.tool_settings) == 3
        assert settings.get_tool_settings("rect")["color"] == "#ff0000"
        assert settings.get_tool_settings("ellipse")["width"] == 5
        assert settings.get_tool_settings("arrow")["color"] == "#0000ff"

    def test_update_existing_tool_settings(self, temp_settings_dir):
        """测试更新已存在的工具设置"""
        settings = AppSettings()
        settings.save_tool_settings("rect", {"color": "#ff0000", "width": 3})
        settings.save_tool_settings("rect", {"color": "#00ff00", "width": 5})

        tool_settings = settings.get_tool_settings("rect")
        assert tool_settings["color"] == "#00ff00"
        assert tool_settings["width"] == 5

    def test_save_tool_settings_saves(self, temp_settings_dir):
        """测试保存工具设置会自动保存"""
        settings = AppSettings()
        settings.save_tool_settings("rect", {"color": "#ff0000", "width": 3})

        # 重新加载设置，验证已保存
        loaded = AppSettings.reload()
        assert loaded.get_tool_settings("rect")["color"] == "#ff0000"


class TestUXConfigDefaults:
    def test_enable_toast_default(self):
        """测试Toast提示默认启用"""
        settings = AppSettings()
        assert settings.enable_toast is True

    def test_toast_duration_default(self):
        """测试Toast持续时间默认2000ms"""
        settings = AppSettings()
        assert settings.toast_duration == 2000

    def test_show_hotkey_tip_default(self):
        """测试快捷键提示默认显示"""
        settings = AppSettings()
        assert settings.show_hotkey_tip is True
