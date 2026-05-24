# macOS Tesseract 打包说明

## 当前状态 ✅

macOS 构建（`build_macos.py`）**已实现** Tesseract 自动打包：

- 通过 `build_common.py` 中的 `find_tesseract()` 检测 Homebrew 安装路径
- 通过 `prepare_tesseract_bundle()` 复制 Tesseract 二进制、依赖 dylib 和语言包
- 通过 `--add-binary` / `--add-data` 传递给 PyInstaller
- 打包后 `.app` 内的路径为 `_MEIPASS/tesseract/{tesseract,*.dylib,tessdata/}`

用户无需手动安装 Tesseract，.app 开箱即用。

## 工作原理

1. `build_macos.py` → `find_tesseract()`
   - 检测 `/opt/homebrew/bin/tesseract` (Apple Silicon) 或 `/usr/local/bin/tesseract` (Intel)
2. `prepare_tesseract_bundle()`
   - 复制 tesseract 二进制到临时目录
   - 递归收集 Homebrew dylib 依赖 → `_collect_dylibs()`
   - 修正 dylib 的 @rpath 为 @loader_path → `_patch_rpaths()`
   - 复制语言包（eng, chi_sim）
3. PyInstaller 构建时通过 `--add-binary` 将文件放入 `_MEIPASS/tesseract/`
4. 运行时 `engine.py` 的 `setup_bundled_tesseract()` 自动定位并使用打包的 Tesseract
