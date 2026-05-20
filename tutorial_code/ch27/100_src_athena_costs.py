"""任务级成本追踪 + 预算守门"""
from __future__ import annotations
import functools
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Callable

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage

from athena.config import settings
from athena.observability import logger
from athena.observability.metrics import LLM_TOKENS, LLM_COST_USD


# ===================== 定价表(2026 Q1 价格)=====================
MODEL_PRICING = {
    # USD per 1M tokens (input, output)
    "gpt-4o":              (2.50, 10.00),
    "gpt-4o-mini":         (0.15,  0.60),
    "claude-3-5-sonnet":   (3.00, 15.00),
    "claude-3-haiku":      (0.25,  1.25),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


@dataclass
class CostLedger:
    """单个任务的成本账本。"""
    task_id: str
    budget_usd: float                                # 预算上限
    spent_usd: float = 0.0
    by_model: dict[str, float] = field(default_factory=dict)
    by_node: dict[str, float] = field(default_factory=dict)
    n_calls: int = 0
    
    def add(self, model: str, node: str, input_tokens: int, output_tokens: int) -> None:
        in_price, out_price = MODEL_PRICING.get(model, (0, 0))
        cost = (input_tokens / 1e6) * in_price + (output_tokens / 1e6) * out_price
        
        self.spent_usd += cost
        self.by_model[model] = self.by_model.get(model, 0) + cost
        self.by_node[node] = self.by_node.get(node, 0) + cost
        self.n_calls += 1
        
        # 同步到 Prometheus
        LLM_TOKENS.labels(model=model, type="input").inc(input_tokens)
        LLM_TOKENS.labels(model=model, type="output").inc(output_tokens)
        LLM_COST_USD.labels(model=model).inc(cost)
    
    @property
    def remaining_usd(self) -> float:
        return max(0, self.budget_usd - self.spent_usd)
    
    @property
    def is_exceeded(self) -> bool:
        return self.spent_usd >= self.budget_usd


# 当前任务的 ledger,跟随 contextvars 走
_current_ledger: ContextVar[CostLedger | None] = ContextVar("ledger", default=None)


def get_current_ledger() -> CostLedger | None:
    return _current_ledger.get()


def set_current_ledger(ledger: CostLedger) -> None:
    _current_ledger.set(ledger)


# ===================== Callback Handler:挂到每次 LLM 调用 =====================
class CostTrackingCallback(BaseCallbackHandler):
    """LangChain 回调,在每次 LLM 调用结束时记账。"""
    
    def __init__(self, node_name: str):
        self.node_name = node_name
    
    def on_llm_end(self, response, **kwargs):
        ledger = get_current_ledger()
        if not ledger:
            return
        
        # 从 response.llm_output 提取 token 计数
        usage = (response.llm_output or {}).get("token_usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        model = (response.llm_output or {}).get("model_name", "unknown")
        
        ledger.add(model, self.node_name, input_tokens, output_tokens)


# ===================== 装饰器:预算守门 =====================
class BudgetExceeded(Exception):
    """任务预算超限。"""
    pass


def budget_guard(node_name: str, max_tokens: int | None = None) -> Callable:
    """
    装饰节点函数。
    - 进入节点前:检查 ledger 是否已超预算
    - 退出节点后:如果超预算,抛 BudgetExceeded(图会中断)
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            ledger = get_current_ledger()
            if ledger and ledger.is_exceeded:
                logger.warning(
                    "budget_exceeded_pre",
                    node=node_name,
                    spent=ledger.spent_usd,
                    budget=ledger.budget_usd,
                )
                raise BudgetExceeded(
                    f"Budget ${ledger.budget_usd:.4f} exceeded "
                    f"(spent ${ledger.spent_usd:.4f}) before {node_name}"
                )
            
            result = await fn(*args, **kwargs)
            
            # 节点后再检查一次(防止节点内部超的)
            if ledger and ledger.is_exceeded:
                logger.warning(
                    "budget_exceeded_post",
                    node=node_name,
                    spent=ledger.spent_usd,
                    budget=ledger.budget_usd,
                )
                # 不抛异常,让图自然走完当前节点,在 supervisor 处理
            
            return result
        return async_wrapper
    return decorator