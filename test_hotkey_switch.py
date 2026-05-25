#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试快捷键切换功能"""

import sys
import time
from PySide6.QtWidgets import QApplication
from src.core.hotkeys import HotkeyListener

def test_hotkey_switch():
    """测试快捷键切换"""
    app = QApplication(sys.argv)

    print("=" * 60)
    print("测试快捷键切换功能")
    print("=" * 60)

    # 测试 1: 创建第一个监听器
    print("\n[测试 1] 创建第一个监听器: F12")
    listener1 = HotkeyListener("f12")
    listener1.capture_signal.connect(lambda: print("  → F12 被触发！"))
    listener1.start()
    print("  ✓ 监听器已启动，请按 F12 测试...")
    time.sleep(3)

    # 测试 2: 停止第一个监听器
    print("\n[测试 2] 停止第一个监听器")
    listener1.stop()
    print("  ✓ stop() 已调用")
    time.sleep(1)  # 等待线程退出

    # 测试 3: 创建第二个监听器
    print("\n[测试 3] 创建第二个监听器: Ctrl+Shift+X")
    listener2 = HotkeyListener("ctrl+shift+x")
    listener2.capture_signal.connect(lambda: print("  → Ctrl+Shift+X 被触发！"))
    listener2.start()
    print("  ✓ 新监听器已启动")

    print("\n" + "=" * 60)
    print("请测试：")
    print("1. 按 F12 → 应该不响应（旧快捷键）")
    print("2. 按 Ctrl+Shift+X → 应该响应（新快捷键）")
    print("=" * 60)
    print("\n等待 10 秒测试...")

    time.sleep(10)

    print("\n清理...")
    listener2.stop()
    print("测试完成")

    app.quit()

if __name__ == "__main__":
    test_hotkey_switch()
