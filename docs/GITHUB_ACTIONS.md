# GitHub Actions 使用指南

## 快速开始

### 查看构建状态

**仓库地址**: https://github.com/lxl3/my_snipaste

1. 打开仓库页面
2. 点击 **Actions** 标签
3. 查看运行中的工作流

---

## 工作流说明

### 自动触发

GitHub Actions 会在以下情况自动运行：

1. **推送标签**（`v*`）
   ```bash
   git tag v1.0.0
   git push github v1.0.0
   ```

2. **手动触发**
   - GitHub 仓库 → Actions → 选择工作流 → Run workflow

### 构建任务

#### 1. Build Windows App
- **环境**: Windows Server 2022
- **Python**: 3.12
- **输出**: `MySnipaste-Windows.zip`
- **时长**: ~8-10 分钟

#### 2. Build macOS App
- **环境**: macOS 13
- **Python**: 3.12
- **输出**: `MySnipaste-macOS.dmg` + `MySnipaste-macOS.zip`
- **时长**: ~10-12 分钟

#### 3. Create Release
- **触发条件**: 标签推送时
- **操作**: 
  - 创建 GitHub Release
  - 上传构建产物

---

## 下载构建产物

### 方式1：从 Actions 下载

1. Actions → 选择运行记录
2. 滚动到底部 → Artifacts
3. 下载：
   - `MySnipaste-Windows`
   - `MySnipaste-macOS`

### 方式2：从 Releases 下载

1. 仓库首页 → Releases
2. 选择版本
3. 下载 Assets 中的安装包

---

## 发布新版本

### 完整流程

```bash
# 1. 更新版本号
# 编辑 src/__init__.py

# 2. 提交更改
git add .
git commit -m "chore: 准备发布 v1.0.0"
git push github master

# 3. 打标签
git tag v1.0.0 -m "Release v1.0.0

新功能：
- 截图、贴图、标注
- OCR 文字识别
- 橡皮擦工具

修复：
- 性能优化
- Bug 修复
"

# 4. 推送标签（触发构建和发布）
git push github v1.0.0

# 5. 等待 12-15 分钟

# 6. 查看 Release
# https://github.com/lxl3/my_snipaste/releases
```

---

## 配置文件

**位置**: `.github/workflows/build-cross-platform.yml`

### 关键配置

```yaml
on:
  push:
    tags:
      - 'v*'              # 标签触发
  workflow_dispatch:      # 手动触发

jobs:
  build-windows:
    runs-on: windows-latest
    # ...

  build-macos:
    runs-on: macos-latest
    # ...

  create-release:
    needs: [build-windows, build-macos]
    # 创建 GitHub Release
```

---

## 故障排除

### Q: Actions 没有运行？

**A**: 检查：
1. Actions 是否启用（Settings → Actions → Allow all actions）
2. 标签是否正确推送（`git tag -l`）
3. 工作流文件是否存在（`.github/workflows/build-cross-platform.yml`）

### Q: 构建失败？

**A**: 查看日志：
1. Actions → 失败的运行
2. 点击失败的任务
3. 查看详细日志

常见问题：
- **依赖安装失败**: 检查 `requirements.txt`
- **文件路径错误**: 确认所有资源文件存在
- **权限不足**: 检查 `GITHUB_TOKEN` 权限

### Q: Release 没有创建？

**A**: 
- Release 只在推送 `v*` 标签时创建
- 检查 `create-release` 任务是否成功
- 确保前置任务（build-windows, build-macos）都成功

---

## 高级功能

### 自定义构建

编辑 `.github/workflows/build-cross-platform.yml`：

```yaml
# 修改 Python 版本
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'  # 改为 3.11

# 添加测试步骤
- name: Run tests
  run: pytest tests/

# 修改 artifact 名称
- uses: actions/upload-artifact@v4
  with:
    name: MySnipaste-Windows-v${{ github.ref_name }}
```

### 条件执行

只在主分支构建：

```yaml
on:
  push:
    branches:
      - master
    tags:
      - 'v*'
```

### 构建缓存

加速依赖安装：

```yaml
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
```

---

## 对比：Gitee Go vs GitHub Actions

| 功能 | Gitee Go | GitHub Actions |
|------|----------|----------------|
| Windows 构建 | ❌ 不支持 | ✅ 支持 |
| macOS 构建 | ❌ 不支持 | ✅ 支持 |
| Linux 构建 | ✅ 支持 | ✅ 支持 |
| 免费额度 | 2000 分钟/月 | 2000 分钟/月 |
| 并发任务 | 有限 | 20+ |
| Marketplace | 少 | 丰富 |

**结论**: GitHub Actions 更适合跨平台构建。

---

## 监控和通知

### 徽章

在 `README.md` 中添加构建状态徽章：

```markdown
![Build Status](https://github.com/lxl3/my_snipaste/actions/workflows/build-cross-platform.yml/badge.svg)
```

### 邮件通知

构建失败时自动发送邮件：

```yaml
- name: Send notification
  if: failure()
  uses: dawidd6/action-send-mail@v3
  with:
    server_address: smtp.example.com
    server_port: 465
    username: ${{ secrets.MAIL_USERNAME }}
    password: ${{ secrets.MAIL_PASSWORD }}
    subject: Build failed - ${{ github.ref_name }}
    body: Build failed for ${{ github.repository }}
```

---

## 技术支持

- **GitHub Actions 文档**: https://docs.github.com/actions
- **问题反馈**: https://github.com/lxl3/my_snipaste/issues
- **构建日志**: Actions → 运行记录 → 任务详情
