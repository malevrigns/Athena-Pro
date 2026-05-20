"""所有节点通过这个工厂获取 LLM,自动带成本追踪。"""
from __future__ import annotations
from langchain_openai import ChatOpenAI

from athena.config import settings
from athena.costs import CostTrackingCallback


def get_llm(
    model: str | None = None,
    temperature: float = 0,
    node_name: str = "unknown",
    **kwargs,
) -> ChatOpenAI:
    """构造带成本追踪的 ChatOpenAI。"""
    return ChatOpenAI(
        model=model or settings.default_model,
        temperature=temperature,
        callbacks=[CostTrackingCallback(node_name=node_name)],
        **kwargs,
    )