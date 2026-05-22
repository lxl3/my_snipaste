# 快捷键配置说明

## 🎯 默认快捷键

### 各平台默认设置

| 平台 | 默认快捷键 | 原因 |
|------|-----------|------|
| **Windows** | `F12` | 传统桌面应用常用键，不与系统冲突 |
| **macOS** | `Cmd + Shift + X` | 类似系统截图 (Cmd+Shift+3/4/5)，避免F12被系统占用 |
| **Linux** | `F12` | 与 Windows 保持一致 |

### 为什么 macOS 不用 F12？

1. **系统占用**
   - F12 在 macOS 上默认用于调节音量/亮度
   - 即使设置"使用 F1、F2 等键作为标准功能键"，仍可能被拦截

2. **辅助功能权限**
   - 全局快捷键需要"辅助功能"权限
   - 即使授权，F12 优先级低于系统功能

3. **macOS 惯例**
   - 系统截图使用 `Cmd + Shift + 数字`
   - 第三方应用通常使用 `Cmd + Shift + 字母`
   - 我们选择 `Cmd + Shift + X`（X = sni**X**）

---

## 🔧 自定义快捷键（未来功能）

当前版本使用平台默认快捷键，暂不支持自定义。

**计划支持的格式**：
```python
# 单键
"f12"
"f11"

# 组合键（修饰键 + 字母/数字）
"ctrl+shift+x"     # Windows/Linux
"cmd+shift+a"      # macOS
"alt+s"            # 任意平台

# 修饰键别名
ctrl / control     # Ctrl 键
cmd / command      # macOS Command 键
shift              # Shift 键
alt / option       # Alt/Option 键
```

**配置文件位置**（计划）：
- Windows: `%APPDATA%\MySnipaste\config.json`
- macOS: `~/Library/Application Support/MySnipaste/config.json`
- Linux: `~/.config/MySnipaste/config.json`

---

## 🛠️ macOS 权限设置

### 授予辅助功能权限

1. 打开 **系统偏好设置** / **系统设置**
2. 进入 **安全性与隐私** → **隐私** → **辅助功能**
3. 点击锁图标解锁（需要管理员密码）
4. 添加 **MySnipaste.app** 或 **Terminal.app**（开发模式）
5. 勾选启用

### 检查权限状态

运行应用时会自动检测权限：
- ✅ 权限已授予：快捷键正常工作
- ❌ 权限被拒绝：显示提示对话框

### 权限仍不生效？

如果授予权限后快捷键仍不工作：

1. **重启应用**
   ```bash
   # 开发模式
   python main.py
   
   # .app 模式
   重新打开 MySnipaste.app
   ```

2. **检查快捷键冲突**
   - 系统偏好设置 → 键盘 → 快捷键
   - 查看是否有其他应用占用同样的快捷键

3. **使用备用方案**
   - ✅ **点击托盘图标**（最可靠）
   - ✅ 应用在前台时使用快捷键
   - ✅ 右键托盘菜单选择"截屏"

---

## 🔍 技术实现

### 快捷键监听

使用 [`pynput`](https://pypi.org/project/pynput/) 库实现全局快捷键：

```python
from pynput import keyboard

# 监听 Cmd+Shift+X (macOS)
required_keys = {keyboard.Key.cmd, keyboard.Key.shift_l, keyboard.KeyCode.from_char('x')}

def on_press(key):
    current_keys.add(key)
    if required_keys.issubset(current_keys):
        trigger_screenshot()

def on_release(key):
    current_keys.discard(key)
```

### 平台检测

```python
import sys

if sys.platform == 'darwin':
    # macOS
    hotkey = 'cmd+shift+x'
elif sys.platform == 'win32':
    # Windows
    hotkey = 'f12'
else:
    # Linux
    hotkey = 'f12'
```

---

## 🐛 故障排除

### Q: macOS 上快捷键不工作

**A**: 检查以下几点：

1. 辅助功能权限是否已授予？
   ```
   系统偏好设置 → 安全性与隐私 → 辅助功能
   ```

2. 快捷键是否被其他应用占用？
   ```
   系统偏好设置 → 键盘 → 快捷键 → App 快捷键
   ```

3. 尝试备用方案：
   - 点击托盘图标截图
   - 应用在前台时使用快捷键

### Q: Windows 上 F12 不工作

**A**: 可能原因：

1. **浏览器占用**
   - 如果浏览器在前台，F12 会打开开发者工具
   - 解决：最小化浏览器或切换到其他窗口

2. **权限不足**
   - 某些防病毒软件可能拦截全局快捷键
   - 解决：将 MySnipaste 添加到白名单

3. **其他应用占用**
   - 检查是否有其他截图软件在运行
   - 解决：关闭其他截图软件

### Q: 能否自定义快捷键？

**A**: 当前版本（v1.0.x）使用固定的平台默认快捷键。

计划在 **v1.1.0** 添加自定义快捷键功能：
- 图形界面配置
- 支持任意组合键
- 快捷键冲突检测

---

## 📚 相关资源

- [pynput 文档](https://pynput.readthedocs.io/)
- [macOS 辅助功能权限](https://support.apple.com/zh-cn/guide/mac-help/mh43185/mac)
- [Windows 全局快捷键](https://docs.microsoft.com/en-us/windows/win32/inputdev/keyboard-input)

---

## 💡 最佳实践

### 推荐使用方式

1. **主要方式**：点击托盘图标
   - ✅ 最可靠，所有平台通用
   - ✅ 无需记忆快捷键
   - ✅ 不受权限限制

2. **辅助方式**：全局快捷键
   - ⚡ 快速启动
   - 💡 需要正确配置权限
   - 🎯 适合频繁使用

3. **备用方式**：托盘右键菜单
   - 📋 查看可用功能
   - 🔍 访问 OCR 等高级功能
   - ⚙️ 退出应用

### 开发者建议

如果您要分发应用给其他用户：

1. **macOS**
   - 使用 `Cmd + Shift + X`（已设置）
   - 在首次启动时引导用户授予辅助功能权限
   - 提供"点击托盘图标"作为备用方案

2. **Windows**
   - 继续使用 `F12`（无冲突）
   - 首次启动时显示快捷键提示
   - 在安装程序中说明快捷键

3. **跨平台**
   - 在 UI 中动态显示当前平台的快捷键
   - 文档中明确说明各平台的快捷键
   - 考虑添加快捷键自定义功能
