"""结构化日志配置"""
from __future__ import annotations
import logging
import sys

import structlog

from athena.config import settings


def configure_logging() -> None:
    """配置 structlog,JSON 输出到 stdout(给容器化部署用)。"""
    
    # 共享处理器
    shared_processors = [
        structlog.contextvars.merge_contextvars,         # 把 contextvars 合并进 log
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    if settings.env == "production":
        # 生产用 JSON
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # 开发用彩色控制台
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()