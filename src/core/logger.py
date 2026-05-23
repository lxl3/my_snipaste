"""增强的日志系统 - 支持颜色输出和日志轮转。"""

import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
import getpass

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
        name: 日志记录器名称
        level: 日志级别
        enable_colors: 是否在控制台启用颜色（Windows/Linux 均支持）

    Features:
        - 控制台输出带颜色（可选）
        - 按大小轮转日志文件（每个文件最大 5MB，保留 5 个备份）
        - 单独的错误日志文件
        - 自动创建按日期命名的日志目录
    """
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

    try:
        all_log_file = os.path.join(daily_log_dir, "app.log")
        all_handler = RotatingFileHandler(
            all_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding="utf-8"
        )
        all_handler.setLevel(logging.DEBUG)
        all_handler.setFormatter(file_formatter)
        logger.addHandler(all_handler)

        error_log_file = os.path.join(daily_log_dir, "error.log")
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)

    except Exception as e:
        print(f"Warning: cannot create log file: {e}", file=sys.stderr)

    # ─── /tmp/ fallback (for packaged app) ───
    try:
        tmp_log = "/tmp/my_snipaste.log"
        tmp_handler = RotatingFileHandler(
            tmp_log,
            maxBytes=2 * 1024 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        tmp_handler.setLevel(logging.DEBUG)
        tmp_handler.setFormatter(file_formatter)
        logger.addHandler(tmp_handler)
    except Exception:
        pass

    return logger


# Pre-defined loggers
logger = setup_logger()


def get_logger(name):
    """获取指定名称的日志记录器（继承主配置）"""
    return logging.getLogger(f"MySnipaste.{name}")


def get_log_dir() -> str:
    return _LOG_DIR


def get_current_log_path() -> str | None:
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(_LOG_DIR, today, "app.log")
    return path if os.path.exists(path) else None
