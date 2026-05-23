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

    # 等级颜色
    DEBUG = "\033[36m"      # 青色
    INFO = "\033[32m"       # 绿色
    WARNING = "\033[33m"    # 黄色
    ERROR = "\033[31m"      # 红色
    CRITICAL = "\033[35m"   # 紫色

    # 组件颜色
    TIME = "\033[90m"       # 灰色
    NAME = "\033[94m"       # 蓝色


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
        # 保存原始 levelname
        levelname_orig = record.levelname

        # 添加颜色
        level_color = self.LEVEL_COLORS.get(record.levelno, LogColors.RESET)
        record.levelname = f"{level_color}{record.levelname:8s}{LogColors.RESET}"

        # 格式化时间（灰色）
        record.asctime = self.formatTime(record, self.datefmt)
        colored_time = f"{LogColors.TIME}{record.asctime}{LogColors.RESET}"

        # 格式化名称（蓝色）
        colored_name = f"{LogColors.NAME}{record.name}{LogColors.RESET}"

        # 构建最终消息
        message = f"{colored_time} [{record.levelname}] {colored_name}: {record.getMessage()}"

        # 处理异常
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            message = f"{message}\n{record.exc_text}"
        if record.stack_info:
            message = f"{message}\n{self.formatStack(record.stack_info)}"

        # 恢复原始 levelname
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

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # ========== 控制台 Handler（彩色） ==========
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if enable_colors and (sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ):
        # Windows Terminal、Linux、macOS 支持颜色
        console_formatter = ColoredFormatter(
            datefmt="%H:%M:%S"
        )
    else:
        # 降级到普通格式
        console_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%H:%M:%S"
        )

    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # ========== 文件 Handler（按大小轮转） ==========
    global _LOG_DIR
    if getattr(sys, 'frozen', False):
        _LOG_DIR = os.path.expanduser("~/Library/Logs/MySnipaste")
    else:
        _LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    log_dir = _LOG_DIR

    # 创建按日期命名的子目录
    today = datetime.now().strftime("%Y-%m-%d")
    daily_log_dir = os.path.join(log_dir, today)
    os.makedirs(daily_log_dir, exist_ok=True)

    # 文件格式化器（无颜色）
    file_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    try:
        # 1. 主日志文件（所有级别）- 轮转
        all_log_file = os.path.join(daily_log_dir, "app.log")
        all_handler = RotatingFileHandler(
            all_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,              # 保留 5 个备份
            encoding="utf-8"
        )
        all_handler.setLevel(logging.DEBUG)
        all_handler.setFormatter(file_formatter)
        logger.addHandler(all_handler)

        # 2. 错误日志文件（只记录 ERROR 和 CRITICAL）- 轮转
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
        # 如果无法写入日志文件，在控制台警告但不中断程序
        print(f"警告: 无法创建日志文件: {e}", file=sys.stderr)

    return logger


# 预定义的日志记录器
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
