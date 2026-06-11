"""增强的日志系统 - 支持颜色输出和日志轮转。"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

_LOG_DIR: str = ""


class LogColors:
    """日志颜色配置"""
    RESET = "\033[0m"
    BOLD = "\033[1m"

    DEBUG = "\033[36m"
    INFO = "\033[32m"
    WARNING = "\033[33m"
    ERROR = "\033[31m"
    CRITICAL = "\033[35m"

    TIME = "\033[90m"
    NAME = "\033[94m"


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器（仅用于控制台）"""

    LEVEL_COLORS = {
        logging.DEBUG: LogColors.DEBUG,
        logging.INFO: LogColors.INFO,
        logging.WARNING: LogColors.WARNING,
        logging.ERROR: LogColors.ERROR,
        logging.CRITICAL: LogColors.CRITICAL,
    }

    def format(self, record):
        levelname_orig = record.levelname
        level_color = self.LEVEL_COLORS.get(record.levelno, LogColors.RESET)
        record.levelname = f"{level_color}{record.levelname:8s}{LogColors.RESET}"

        record.asctime = self.formatTime(record, self.datefmt)
        colored_time = f"{LogColors.TIME}{record.asctime}{LogColors.RESET}"
        colored_name = f"{LogColors.NAME}{record.name}{LogColors.RESET}"
        message = f"{colored_time} [{record.levelname}] {colored_name}: {record.getMessage()}"

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            message = f"{message}\n{record.exc_text}"
        if record.stack_info:
            message = f"{message}\n{self.formatStack(record.stack_info)}"

        record.levelname = levelname_orig

        return message


def setup_logger(name="MySnipaste", level=logging.DEBUG, enable_colors=True):
    """配置并返回增强的日志记录器

    Args:
        name: 日志记录器名称，非 "MySnipaste" 时自动作为子 logger
        level: 日志级别
        enable_colors: 是否在控制台启用颜色（Windows/Linux 均支持）

    Features:
        - 控制台输出带颜色（可选）
        - 按大小轮转日志文件（每个文件最大 5MB，保留 5 个备份）
        - 单独的错误日志文件
        - 自动创建按日期命名的日志目录
    """
    # 非主 logger 时返回子 logger（继承父 logger 的 handlers）
    if name != "MySnipaste":
        return get_logger(name)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    # ─── Console handler (colored) ───
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if enable_colors and (sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ):
        console_formatter = ColoredFormatter(
            datefmt="%H:%M:%S"
        )
    else:
        console_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%H:%M:%S"
        )

    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # ─── File handler (rotating) ───
    global _LOG_DIR
    if getattr(sys, 'frozen', False):
        _LOG_DIR = os.path.expanduser("~/Library/Logs/MySnipaste")
    else:
        _LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    log_dir = _LOG_DIR

    today = datetime.now().strftime("%Y-%m-%d")
    daily_log_dir = os.path.join(log_dir, today)
    os.makedirs(daily_log_dir, exist_ok=True)

    file_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    class SafeRotatingFileHandler(RotatingFileHandler):
        """轮转失败时不崩溃——Windows 上前进程残留句柄会导致 PermissionError。"""

        def doRollover(self):
            try:
                super().doRollover()
            except OSError:
                pass  # 锁住了就跳过轮转，继续写当前文件

        def _open(self):
            try:
                return super()._open()
            except OSError:
                import io
                return io.StringIO()  # 哑 fallback，不丢失日志流

    def _make_handler(path: str, level: int, mb: int, count: int) -> logging.Handler | None:
        try:
            h = SafeRotatingFileHandler(
                path, maxBytes=mb * 1024 * 1024, backupCount=count,
                encoding="utf-8", delay=True
            )
            h.setLevel(level)
            h.setFormatter(file_formatter)
            return h
        except Exception as e:
            print(f"  cannot create log handler {path}: {e}", file=sys.stderr)
            return None

    all_log_file = os.path.join(daily_log_dir, "app.log")
    all_handler = _make_handler(all_log_file, logging.DEBUG, 5, 5)
    if all_handler:
        logger.addHandler(all_handler)

    error_log_file = os.path.join(daily_log_dir, "error.log")
    error_handler = _make_handler(error_log_file, logging.ERROR, 5, 5)
    if error_handler:
        logger.addHandler(error_handler)

    # ─── /tmp/ fallback (for packaged app) ───
    try:
        tmp_log = "/tmp/my_snipaste.log"
        tmp_handler = SafeRotatingFileHandler(
            tmp_log,
            maxBytes=2 * 1024 * 1024,
            backupCount=2,
            encoding="utf-8",
            delay=True,
        )
        tmp_handler.setLevel(logging.DEBUG)
        tmp_handler.setFormatter(file_formatter)
        logger.addHandler(tmp_handler)
    except Exception:
        pass

    return logger


# Pre-defined loggers
logger = setup_logger()


def apply_log_level(level_str: str) -> None:
    """Apply a log level string (DEBUG/INFO/WARNING/ERROR) to all MySnipaste loggers at runtime.

    Updates both the logger levels and handler levels, except for error.log handlers
    which always remain at ERROR level.
    """
    level = getattr(logging, level_str.upper(), logging.DEBUG)

    # Update all loggers that start with "MySnipaste"
    for name, lg in logging.Logger.manager.loggerDict.items():
        if isinstance(lg, logging.Logger) and name.startswith("MySnipaste"):
            lg.setLevel(level)
            for handler in lg.handlers:
                # Keep error.log handler at ERROR level
                if isinstance(handler, logging.FileHandler):
                    try:
                        if handler.baseFilename.endswith("error.log"):
                            continue
                    except AttributeError:
                        pass
                handler.setLevel(level)

    # Also update the main MySnipaste logger (may not be in loggerDict if not a PlaceHolder)
    main_logger = logging.getLogger("MySnipaste")
    main_logger.setLevel(level)
    for handler in main_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            try:
                if handler.baseFilename.endswith("error.log"):
                    continue
            except AttributeError:
                pass
        handler.setLevel(level)


def get_logger(name):
    """获取指定名称的日志记录器（继承主配置）"""
    return logging.getLogger(f"MySnipaste.{name}")


def get_log_dir() -> str:
    return _LOG_DIR


def get_current_log_path() -> str | None:
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(_LOG_DIR, today, "app.log")
    return path if os.path.exists(path) else None
