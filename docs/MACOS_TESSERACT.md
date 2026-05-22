# macOS Tesseract 打包方案

## 当前状态

macOS 构建的 `.app` 不包含 Tesseract 二进制文件，用户需要自行安装。

## 改进方案

### 方案 1：打包 Tesseract 到 .app（推荐）

修改 `scripts/build_macos.py`，将 Homebrew 安装的 Tesseract 打包进去：

```python
import shutil

def bundle_tesseract():
    """将 Tesseract 和语言包打包到 .app"""
    # 检测 Homebrew 路径（Intel vs Apple Silicon）
    tesseract_paths = [
        "/opt/homebrew/bin/tesseract",  # Apple Silicon
        "/usr/local/bin/tesseract",     # Intel
    ]
    
    tesseract_bin = None
    for path in tesseract_paths:
        if os.path.exists(path):
            tesseract_bin = path
            break
    
    if not tesseract_bin:
        print("⚠️ Tesseract 未安装，OCR 功能将不可用")
        return False
    
    # Tesseract 数据目录
    tessdata_paths = [
        "/opt/homebrew/share/tessdata",
        "/usr/local/share/tessdata",
    ]
    
    tessdata_dir = None
    for path in tessdata_paths:
        if os.path.exists(path):
            tessdata_dir = path
            break
    
    if not tessdata_dir:
        print("⚠️ Tesseract 语言包未找到")
        return False
    
    # 在 .app 中创建 tesseract 目录
    app_contents = DIST_DIR / f"{BUILD_NAME}.app" / "Contents"
    tess_bundle_dir = app_contents / "Resources" / "tesseract"
    tess_bundle_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制 Tesseract 二进制文件
    shutil.copy2(tesseract_bin, tess_bundle_dir / "tesseract")
    
    # 复制语言包（只复制需要的：eng, chi_sim）
    tessdata_bundle = tess_bundle_dir / "tessdata"
    tessdata_bundle.mkdir(exist_ok=True)
    for lang in ["eng", "chi_sim"]:
        lang_file = f"{lang}.traineddata"
        src = Path(tessdata_dir) / lang_file
        if src.exists():
            shutil.copy2(src, tessdata_bundle / lang_file)
    
    print(f"✓ Tesseract 已打包到 .app")
    return True
```

然后在 PyInstaller 命令中添加：

```python
cmd = [
    "pyinstaller",
    "--name", BUILD_NAME,
    "--onefile",
    "--windowed",
    "--icon", str(PROJECT_DIR / "icon.icns"),
    
    # 打包 Tesseract
    "--add-binary", f"{tess_bundle_dir / 'tesseract'}:tesseract",
    "--add-data", f"{tess_bundle_dir / 'tessdata'}:tesseract/tessdata",
    
    # ... 其他参数
]
```

**优点**：
- ✅ 用户开箱即用，无需额外安装
- ✅ 与 Windows 版本体验一致

**缺点**：
- ❌ .app 体积增大（约 30-50MB）
- ❌ 需要处理不同架构（Intel/Apple Silicon）

---

### 方案 2：运行时自动下载（可选）

检测到 Tesseract 未安装时，提示用户自动安装：

```python
def prompt_install_tesseract():
    """提示用户安装 Tesseract"""
    msg = QMessageBox()
    msg.setWindowTitle("OCR 功能需要 Tesseract")
    msg.setText("检测到 Tesseract OCR 引擎未安装")
    msg.setInformativeText(
        "OCR 文字识别功能需要 Tesseract 引擎支持。\n\n"
        "请在终端运行以下命令安装：\n"
        "brew install tesseract tesseract-lang\n\n"
        "安装后重启应用即可使用 OCR 功能。"
    )
    msg.setIcon(QMessageBox.Information)
    msg.addButton("复制命令", QMessageBox.ActionRole)
    msg.addButton("稍后安装", QMessageBox.RejectRole)
    
    if msg.exec() == 0:  # 复制命令
        QApplication.clipboard().setText("brew install tesseract tesseract-lang")
```

**优点**：
- ✅ .app 体积小
- ✅ 用户自主选择

**缺点**：
- ❌ 需要用户手动操作
- ❌ 体验不如方案 1 流畅

---

## 推荐方案

**对于发布版本**：使用**方案 1**（打包 Tesseract）
- 提供最佳用户体验
- 避免用户配置问题
- 与 Windows 版本一致

**对于开发版本**：提示用户安装（方案 2）
- 减少构建时间
- 方便开发调试

---

## 实施步骤

如果您决定采用方案 1，我可以：

1. 修改 `scripts/build_macos.py` 添加 Tesseract 打包逻辑
2. 更新 GitHub Actions 工作流确保正确打包
3. 测试不同 macOS 架构（Intel/Apple Silicon）
4. 更新文档说明打包后的 .app 已包含 OCR 引擎

是否需要我实施这个改进？
