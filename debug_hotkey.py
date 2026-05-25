#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试快捷键解析和监听"""

import sys
import time
from pynput import keyboard

def test_parse_hotkey(hotkey_str):
    """测试快捷键解析"""
    print(f"\n解析快捷键: {hotkey_str}")
    parts = hotkey_str.lower().split('+')
    keys = set()

    for part in parts:
        part = part.strip()
        if part in ('ctrl', 'control'):
            keys.add(keyboard.Key.ctrl_l)
            print(f"  + Ctrl")
        elif part in ('cmd', 'command', 'super'):
            keys.add(keyboard.Key.cmd)
            print(f"  + Cmd")
        elif part in ('shift'):
            keys.add(keyboard.Key.shift_l)
            print(f"  + Shift")
        elif part in ('alt', 'option'):
            keys.add(keyboard.Key.alt_l)
            print(f"  + Alt")
        elif part.startswith('f') and part[1:].isdigit():
            key_num = int(part[1:])
            keys.add(getattr(keyboard.Key, f'f{key_num}'))
            print(f"  + F{key_num}")
        elif len(part) == 1 and part.isalpha():
            keys.add(keyboard.KeyCode.from_char(part))
            print(f"  + {part.upper()}")
        else:
            print(f"  ! 无法识别: {part}")

    print(f"解析结果: {keys}")
    return keys

def test_listen(hotkey_str):
    """测试监听"""
    print(f"\n开始监听快捷键: {hotkey_str}")
    print("按任意键查看捕获的按键...")
    print("按 ESC 退出")

    required_keys = test_parse_hotkey(hotkey_str)
    current_keys = set()

    def normalize(key):
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return keyboard.Key.ctrl_l
        elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
            return keyboard.Key.shift_l
        elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            return keyboard.Key.alt_l
        return key

    def on_press(key):
        normalized = normalize(key)
        current_keys.add(normalized)
        print(f"[按下] {key} -> {normalized}")
        print(f"  当前按键集合: {current_keys}")

        if required_keys.issubset(current_keys):
            print(f"  *** 快捷键匹配！***")

        if key == keyboard.Key.esc:
            print("\n退出监听")
            return False

    def on_release(key):
        normalized = normalize(key)
        current_keys.discard(normalized)
        print(f"[释放] {key} -> {normalized}")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

if __name__ == "__main__":
    print("=" * 60)
    print("快捷键调试工具")
    print("=" * 60)

    # 测试几个常见的快捷键
    test_cases = [
        "f12",
        "ctrl+shift+x",
        "ctrl+shift+a",
        "alt+s",
    ]

    print("\n[1] 测试快捷键解析")
    for hotkey in test_cases:
        test_parse_hotkey(hotkey)

    print("\n" + "=" * 60)
    print("[2] 实时监听测试")
    print("=" * 60)

    hotkey = input("\n输入要测试的快捷键 (如 ctrl+shift+x): ").strip() or "ctrl+shift+x"
    test_listen(hotkey)
