# MySnipaste 构建指南

## 本地构建

### Windows

```bash
# 安装依赖
pip install -r requirements.txt

# 构建（自动下载 Tesseract）
python scripts/build_windows.py

# 输出：dist/MySnipaste.exe
```

### macOS

```bash
# 安装系统依赖
brew install tesseract tesseract-lang

# 安装 Python 依赖
pip install -r requirements.txt

# 构建
python scripts/build_macos.py

# 输出：dist/MySnipaste.app
```

---

## 自动构建（CI/CD）

### Gitee Go 自动构建（当前平台）

**方式1：手动触发**

1. 打开 Gitee 仓库页面
2. 进入 **流水线** (Pipeline) 标签
3. 点击 **运行流水线**
4. 等待构建完成（约5-10分钟）
5. 下载构建产物

**方式2：版本发布（推荐）**

```bash
# 打标签并推送（自动触发构建和发布）
git tag v1.0.0
git push origin v1.0.0

# Gitee 会自动：
# 1. 构建 Windows 和 macOS 版本
# 2. 创建 Gitee Release
# 3. 上传安装包到 Release
```

### GitHub Actions 自动构建（可选）

如果您也将代码推送到 GitHub：

```bash
# 添加 GitHub 远程仓库
git remote add github https://github.com/your-username/my_snipaste.git
git push github master

# 打标签触发构建
git tag v1.0.0
git push github v1.0.0
```

### 构建产物

- **Windows**: `MySnipaste-Windows.zip`
- **macOS**: `MySnipaste-macOS.zip`
- **GitHub 额外**: `MySnipaste-macOS.dmg` (仅 GitHub Actions)

---

## 初次设置

### Gitee Go 设置

**1. 推送配置**

```bash
git add .gitee/workflows/build.yml
git add scripts/build_macos.py
git add docs/BUILD.md
git commit -m "ci: 添加 Gitee Go 构建工作流"
git push origin master
```

**2. 启用 Gitee Go**

1. 打开 Gitee 仓库页面
2. 进入 **服务** → **Gitee Go**
3. 点击 **启用 Gitee Go**
4. 授权必要的权限

**3. 测试构建**

- Gitee 仓库 → 流水线 → 运行流水线

**4. 发布版本**

```bash
git tag v1.0.0
git push origin v1.0.0

# 查看 Gitee Releases 页面
```

---

### GitHub Actions 设置（可选）

如果您需要同时在 GitHub 上构建：

```bash
# 添加 GitHub 远程仓库
git remote add github https://github.com/your-username/my_snipaste.git

# 推送所有内容
git push github master
git push github --tags

# GitHub → Actions 会自动运行
```

---

## 常见问题

### Q: GitHub Actions 构建失败？

**A:** 检查日志中的错误信息：
- **依赖问题**：查看 `requirements.txt` 是否完整
- **权限问题**：确保 `GITHUB_TOKEN` 有发布权限
- **文件路径**：确认所有资源文件路径正确

### Q: macOS 打包后无法运行？

**A:** 可能的原因：
1. **代码签名**：macOS 未签名应用需要右键打开
2. **权限问题**：运行 `chmod +x MySnipaste.app/Contents/MacOS/*`
3. **Tesseract 路径**：确保应用能找到 Tesseract

### Q: 如何自定义图标？

**A:** 
- **Windows**: 替换 `icon.ico`
- **macOS**: 替换 `icon.icns` 或放置 256x256 PNG 到 `assets/icons/icon-256.png`

---

## 高级选项

### 自定义版本号

编辑 `.github/workflows/build-cross-platform.yml`：

```yaml
env:
  VERSION: "1.0.0"  # 自定义版本号
```

### 修改构建配置

编辑 \`scripts/build_windows.py\`（Windows）或 \`scripts/build_macos.py\`（macOS）调整：
- 应用名称
- 图标路径
- 打包选项
- 额外数据文件

---

## 发布清单

发布新版本前检查：

- [ ] 更新 `src/__init__.py` 中的版本号
- [ ] 更新 `README.md` 的功能说明
- [ ] 测试所有核心功能
- [ ] 检查依赖是否更新
- [ ] 编写 Release Notes
- [ ] 打标签并推送

```bash
# 完整发布流程
git add .
git commit -m "chore: release v1.0.0"
git push

git tag v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```
