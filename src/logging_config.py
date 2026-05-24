"""
日志配置

在项目启动时调用 setup_logging() 配置全局日志：
- 控制台：INFO 级别，带颜色、时间戳、模块名
- 文件：DEBUG 级别，写入 logs/mao.log
"""

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""

    # ANSI 颜色码
    COLORS = {
        "DEBUG": "\033[36m",      # 青色
        "INFO": "\033[32m",       # 绿色
        "WARNING": "\033[33m",    # 黄色
        "ERROR": "\033[31m",      # 红色
        "CRITICAL": "\033[35m",   # 品红
    }
    RESET = "\033[0m"

    def __init__(self, fmt=None, datefmt=None, style="%", use_color=True):
        super().__init__(fmt, datefmt, style)
        self.use_color = use_color and sys.stdout.isatty()

    def format(self, record):
        # 保存原始 levelname
        original_levelname = record.levelname

        if self.use_color:
            color = self.COLORS.get(record.levelname, "")
            record.levelname = f"{color}{record.levelname:<8}{self.RESET}"

        result = super().format(record)

        # 恢复原始 levelname（避免影响其他 formatter）
        record.levelname = original_levelname

        return result


def _build_file_formatter() -> logging.Formatter:
    """文件日志格式化器（不含颜色，更详细）"""
    return logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _build_console_formatter() -> ColoredFormatter:
    """控制台日志格式化器（简短 + 颜色）"""
    return ColoredFormatter(
        "%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def setup_logging(
    level: str = "INFO",
    log_dir: str = None,
    log_file: str = "mao.log",
    console_level: str = None,
) -> None:
    """
    配置全局日志输出。

    Args:
        level: 根日志级别（默认 INFO）
        log_dir: 日志文件目录（默认项目根目录下的 logs/）
        log_file: 日志文件名
        console_level: 控制台单独级别（默认同 level）
    """
    # 确定日志目录
    if log_dir is None:
        # 尝试找到项目根目录
        cwd = Path.cwd()
        log_dir = cwd / "logs"
    else:
        log_dir = Path(log_dir)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_file

    # 根 logger 配置
    root_level = getattr(logging, level.upper(), logging.INFO)
    console_lvl = getattr(logging, (console_level or level).upper(), root_level)

    # 创建根 logger 处理器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 根设为 DEBUG，handler 过滤

    # 清除已有的 handler（避免重复添加）
    root_logger.handlers.clear()

    # ── 控制台 Handler ──
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_lvl)
    console_handler.setFormatter(_build_console_formatter())
    root_logger.addHandler(console_handler)

    # ── 文件 Handler ──
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_build_file_formatter())
    root_logger.addHandler(file_handler)

    # ── 抑制第三方库的 DEBUG 噪音 ──
    noisy_loggers = [
        "httpx", "httpcore", "urllib3", "openai", "anthropic",
        "langchain", "langgraph", "PIL", "watchfiles",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)

    # 验证
    logger = logging.getLogger(__name__)
    logger.debug("日志系统初始化完成 → %s (level=%s, console=%s)",
                 log_path, level, console_level or level)


def get_logger(name: str) -> logging.Logger:
    """便捷函数：获取命名 logger"""
    return logging.getLogger(name)


# 模块导入时不自动初始化，需要显式调用 setup_logging()
