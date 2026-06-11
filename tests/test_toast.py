import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from src.ui.common.toast import ToastNotification, ToastManager

@pytest.fixture(scope="module")
def qapp():
    """Qt应用fixture"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

def test_toast_creation(qapp):
    """测试 Toast 创建"""
    toast = ToastNotification("测试消息", "✓", "success")
    assert toast.message == "测试消息"
    assert toast.icon == "✓"
    assert toast.toast_type == "success"

def test_toast_manager_singleton(qapp):
    """测试 ToastManager 单例"""
    manager1 = ToastManager.instance()
    manager2 = ToastManager.instance()
    assert manager1 is manager2

def test_toast_show(qapp):
    """测试 Toast 显示"""
    ToastManager.show("测试", "✓", "success", duration=100)
    # Toast 应该被添加到管理器
    assert len(ToastManager.instance()._toasts) > 0
