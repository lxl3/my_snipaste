# 日志系统说明

## 功能特性

### 1. 彩色控制台输出

不同日志级别使用不同颜色，便于快速识别：

- 🔵 **DEBUG** - 青色 - 调试信息
- 🟢 **INFO** - 绿色 - 常规信息
- 🟡 **WARNING** - 黄色 - 警告信息
- 🔴 **ERROR** - 红色 - 错误信息
- 🟣 **CRITICAL** - 紫色 - 严重错误

支持平台：
- ✅ Windows Terminal
- ✅ Linux 终端
- ✅ macOS 终端
- ⚠️ 旧版 Windows CMD（自动降级为无色输出）

### 2. 日志文件轮转

避免单个日志文件过大：

- **大小限制**：每个文件最大 5MB
- **备份数量**：保留 5 个历史文件
- **命名规则**：`app.log`, `app.log.1`, `app.log.2`, ...

### 3. 按日期组织

日志文件按日期分目录存储：

```
logs/
├── 2026-05-22/
│   ├── app.log          # 所有级别日志
│   ├── app.log.1        # 备份 1
│   ├── app.log.2        # 备份 2
│   ├── error.log        # 仅错误日志
│   └── error.log.1      # 错误备份
├── 2026-05-23/
│   ├── app.log
│   └── error.log
└── ...
```

### 4. 分级存储

- **app.log** - 记录所有级别（DEBUG、INFO、WARNING、ERROR、CRITICAL）
- **error.log** - 只记录错误和严重错误（ERROR、CRITICAL）

方便快速排查问题，无需翻阅海量日志。

## 使用方法

### 基础使用

```python
from src.core.logger import logger

# 不同级别的日志
logger.debug("调试信息：变量值 x=10")
logger.info("程序启动成功")
logger.warning("配置文件缺少可选项，使用默认值")
logger.error("文件读取失败")
logger.critical("数据库连接断开，程序无法继续")
```

### 模块化日志

为不同模块创建独立的日志记录器：

```python
from src.core.logger import get_logger

# 为截图模块创建日志记录器
screenshot_logger = get_logger("screenshot")
screenshot_logger.info("截图开始")

# 为 OCR 模块创建日志记录器
ocr_logger = get_logger("ocr")
ocr_logger.debug("OCR 引擎初始化")
```

输出示例：
```
12:34:56 [INFO    ] openSnipaste.screenshot: 截图开始
12:34:57 [DEBUG   ] openSnipaste.ocr: OCR 引擎初始化
```

### 记录异常

```python
try:
    result = risky_operation()
except Exception as e:
    logger.exception("操作失败")  # 自动记录完整堆栈跟踪
```

## 配置选项

### 修改日志级别

编辑 `src/core/logger.py`：

```python
# 生产环境：只记录 INFO 及以上
logger = setup_logger(level=logging.INFO)

# 开发环境：记录所有 DEBUG 信息
logger = setup_logger(level=logging.DEBUG)
```

### 禁用颜色输出

```python
logger = setup_logger(enable_colors=False)
```

### 调整文件大小和备份数量

修改 `RotatingFileHandler` 参数：

```python
all_handler = RotatingFileHandler(
    all_log_file,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=10,              # 保留 10 个备份
    encoding="utf-8"
)
```

## 日志格式

### 控制台格式（彩色）

```
13:45:12 [INFO    ] openSnipaste: 程序启动
13:45:13 [WARNING ] openSnipaste.ocr: 检测到低内存
13:45:14 [ERROR   ] openSnipaste.screenshot: 截图失败
```

### 文件格式（带行号）

```
2026-05-22 13:45:12 [INFO    ] openSnipaste:45 - 程序启动
2026-05-22 13:45:13 [WARNING ] openSnipaste.ocr:128 - 检测到低内存
2026-05-22 13:45:14 [ERROR   ] openSnipaste.screenshot:203 - 截图失败
```

## 清理旧日志

可以手动删除过期的日志目录：

```bash
# Windows PowerShell
Get-ChildItem logs -Directory | Where-Object {$_.Name -lt "2026-05-01"} | Remove-Item -Recurse

# Linux/macOS
find logs -type d -name "2026-0[1-4]-*" -exec rm -rf {} +
```

或编写自动清理脚本（保留最近 30 天）。

## 故障排除

### Q: 控制台没有颜色？

**A**: 检查终端支持：
- Windows：使用 Windows Terminal，不要用旧的 CMD
- Linux/macOS：默认支持
- 环境变量：设置 `WT_SESSION` 或 `ANSICON`

### Q: 日志文件过多？

**A**: 
1. 增大 `maxBytes`（减少轮转频率）
2. 减少 `backupCount`（保留更少备份）
3. 定期清理旧日期的目录

### Q: 无法写入日志文件？

**A**: 
- 检查 `logs/` 目录权限
- 程序会在控制台输出警告但不会崩溃
- 至少保证控制台日志可用

## 最佳实践

1. **合理使用日志级别**
   - DEBUG：详细的诊断信息（开发时使用）
   - INFO：确认程序按预期运行
   - WARNING：预期之外但不影响运行
   - ERROR：严重问题导致某功能失败
   - CRITICAL：程序即将崩溃

2. **避免过度日志**
   ```python
   # ❌ 不好：循环中大量日志
   for i in range(10000):
       logger.debug(f"处理第 {i} 项")
   
   # ✅ 好：关键节点记录
   logger.info(f"开始处理 10000 项")
   # ... 处理 ...
   logger.info(f"处理完成，成功 {success_count} 项")
   ```

3. **记录上下文**
   ```python
   # ❌ 不好：信息不足
   logger.error("失败")
   
   # ✅ 好：包含关键信息
   logger.error(f"截图失败：区域 {rect}, 错误 {e}")
   ```

4. **使用异常记录**
   ```python
   # ❌ 不好：只记录消息
   except Exception as e:
       logger.error(f"错误: {e}")
   
   # ✅ 好：记录完整堆栈
   except Exception:
       logger.exception("操作失败")
   ```
