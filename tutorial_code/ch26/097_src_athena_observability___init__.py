"""LangSmith 追踪 - 零侵入接入"""
from __future__ import annotations
import os

from athena.config import settings
from athena.observability.logging import configure_logging, logger


def configure_observability() -> None:
    """启动时调用一次,装好所有观测设施。"""
    # ① 结构化日志
    configure_logging()
    
    # ② LangSmith - 设置环境变量就自动追踪所有 LangChain/LangGraph 调用
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project   # "athena-prod"
        logger.info("langsmith_enabled", project=settings.langsmith_project)
    else:
        logger.warning("langsmith_disabled", reason="no api key configured")
    
    # ③ Prometheus(下面单独讲)
    from athena.observability.metrics import setup_metrics
    setup_metrics()