# Gitee Go 使用指南

## 快速开始

### 1. 启用 Gitee Go

1. 打开仓库：https://gitee.com/xin-lin-lll/opensnipaste
2. 点击 **服务** → **Gitee Go**
3. 点击 **启用 Gitee Go**
4. 授权必要权限

### 2. 手动触发构建

1. 仓库页面 → **流水线** (Pipeline)
2. 点击 **运行流水线**
3. 选择分支：`master`
4. 点击 **运行**
5. 等待约 5-10 分钟

### 3. 下载构建产物

1. 流水线运行完成后
2. 点击运行记录
3. 查看 **产物** (Artifacts)
4. 下载：
   - `openSnipaste-Windows.zip`
   - `openSnipaste-macOS.zip`

---

## 版本发布流程

### 自动发布

```bash
# 1. 更新版本号（可选）
# 编辑 src/__init__.py

# 2. 提交所有更改
git add .
git commit -m "chore: 准备发布 v1.0.0"
git push

# 3. 打标签触发自动构建和发布
git tag v1.0.0
git push origin v1.0.0
```

### 查看发布

1. Gitee 仓库 → **发行版** (Releases)
2. 找到最新版本
3. 下载安装包

---

## 配置说明

### 工作流文件

- **位置**: `.gitee/workflows/build.yml`
- **触发条件**:
  - 推送标签（`v*`）
  - 手动触发

### 构建任务

1. **build-windows**: 构建 Windows 版本
2. **build-macos**: 构建 macOS 版本
3. **create-release**: 创建发布（仅标签触发）

### 构建环境

- **Windows**: `windows-latest`
- **macOS**: `macos-latest`
- **Python**: 3.12

---

## 常见问题

### Q: Gitee Go 免费吗？

**A:** Gitee Go 提供免费额度：
- 个人版：每月 2000 分钟
- 企业版：根据套餐不同

### Q: 构建失败怎么办？

**A:** 检查流水线日志：
1. 进入失败的流水线
2. 查看具体任务的日志
3. 根据错误信息修复

常见问题：
- **依赖安装失败**：检查 `requirements.txt`
- **权限错误**：检查 Gitee Go 授权
- **文件路径错误**：确认所有资源文件存在

### Q: 如何修改构建配置？

**A:** 编辑 `.gitee/workflows/build.yml`：

```yaml
# 修改 Python 版本
- name: 设置 Python 环境
  uses: actions/setup-python@v4
  with:
    python-version: '3.11'  # 改为 3.11

# 添加额外步骤
- name: 运行测试
  run: pytest tests/
```

提交并推送后，下次构建会使用新配置。

### Q: 如何只构建 Windows 或 macOS？

**A:** 注释掉不需要的任务：

```yaml
jobs:
  # build-windows:  # 注释掉 Windows 构建
  #   ...

  build-macos:  # 只保留 macOS 构建
    ...
```

---

## 进阶配置

### 添加构建缓存

加速依赖安装：

```yaml
- name: 缓存 pip 依赖
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

### 发送通知

构建完成后发送通知：

```yaml
- name: 发送通知
  if: always()
  run: |
    curl -X POST "https://api.example.com/notify" \
      -d "status=${{ job.status }}" \
      -d "build=${{ github.run_number }}"
```

### 多分支构建

同时构建多个分支：

```yaml
on:
  push:
    branches:
      - master
      - develop
    tags:
      - 'v*'
```

---

## 技术支持

- **Gitee Go 文档**: https://gitee.com/help/articles/4391
- **问题反馈**: 在仓库创建 Issue
- **构建日志**: 流水线 → 运行记录 → 查看日志
