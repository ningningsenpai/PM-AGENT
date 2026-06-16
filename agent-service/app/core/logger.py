"""统一日志工具。"""

import logging
import os
import sys


class AgentLogger:
    """Agent 服务日志工厂。"""

    _configured = False

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """获取指定名称的 logger，并确保全局日志配置只初始化一次。"""
        cls._configure_once()
        return logging.getLogger(name)

    @classmethod
    def _configure_once(cls) -> None:
        """初始化全局日志格式和输出目标。"""
        if cls._configured:
            return

        level_name = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.handlers.clear()
        root_logger.addHandler(handler)

        cls._configured = True


def get_logger(name: str) -> logging.Logger:
    """获取统一配置的 logger。"""
    return AgentLogger.get_logger(name)
