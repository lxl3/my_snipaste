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

### ⚠️ 重要：打包版本 vs 开发模式

**开发模式（`python main.py`）**：
- 权限主体是 **Terminal.app** 或 **iTerm2.app**
- 如果终端应用已有权限，快捷键可以直接工作

**打包版本（`MySnipaste.app`）**：
- 权限主体是 **MySnipaste.app** 本身
- 需要单独授予 **Input Monitoring** 权限
- 这是最常见的"打包后快捷键不工作"的原因

### 授予 Input Monitoring 权限（必需）

全局快捷键需要此权限才能工作：

1. 打开 **系统设置**（macOS 13+）或 **系统偏好设置**（macOS 12-）
2. 进入 **隐私与安全性** → **输入监控**
3. 点击锁图标解锁（需要管理员密码）
4. 点击 **+** 按钮，选择 **MySnipaste.app**
5. 勾选启用
6. **完全退出并重启应用**（重要！）

**注意**：直接点击窗口关闭按钮不会完全退出，请从托盘菜单选择「退出」。

### 检查权限状态

**方法 1：托盘菜单**
- 右键点击托盘图标
- 选择「检查权限」（macOS only）
- 查看当前权限状态

**方法 2：启动提示**
- 应用启动时会自动检测权限
- ✅ 权限已授予：显示正常启动提示
- ❌ 权限未授予：显示权限提示对话框，带「打开系统设置」按钮

**方法 3：查看日志**
```bash
tail -f logs/$(ls -t logs/ | head -1)/app.log
```
查找类似输出：
```
✓ Input Monitoring 权限已授予（全局快捷键可用）
🎉 所有必需权限已就绪
```

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

### Q: macOS 上快捷键不工作（打包版本）

**A**: 这是最常见的问题，99% 的情况是权限未授予。

**诊断步骤**：

1. **检查权限状态**
   - 从托盘菜单选择「检查权限」
   - 或查看启动时的提示对话框

2. **授予 Input Monitoring 权限**
   ```
   系统设置 → 隐私与安全性 → 输入监控
   → 点击 + → 选择 MySnipaste.app → 勾选启用
   ```

3. **完全退出并重启应用**
   - 从托盘菜单选择「退出」（不要直接关闭窗口）
   - 重新打开 MySnipaste.app

4. **如果还是不行，重置权限数据库**（谨慎操作）
   ```bash
   tccutil reset ListenEvent
   ```
   然后重新打开应用，系统会再次请求权限

5. **最后手段：检查快捷键冲突**
   ```
   系统设置 → 键盘 → 快捷键 → App 快捷键
   ```

**为什么开发模式可以，打包后不行？**

- 开发模式：权限主体是 Terminal.app（已有权限）
- 打包版本：权限主体是 MySnipaste.app（需要单独授权）

### Q: macOS 上快捷键不工作（开发模式）

**A**: 开发模式下权限通常已经授予给终端，如果不工作：

1. 快捷键是否被其他应用占用？
   ```
   系统设置 → 键盘 → 快捷键 → App 快捷键
   ```

2. 尝试备用方案：
   - 点击托盘图标截图
   - 应用在前台时使用 F12 快捷键

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
