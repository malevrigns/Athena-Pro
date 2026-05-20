"""Prometheus 指标采集"""
from __future__ import annotations
import functools
import time
from typing import Callable

from prometheus_client import Counter, Histogram, Gauge


# ===================== 核心业务指标 =====================
TASK_CREATED = Counter(
    "athena_task_created_total",
    "研究任务创建总数",
    ["user_tier"],
)

TASK_COMPLETED = Counter(
    "athena_task_completed_total",
    "任务完成数",
    ["outcome"],                                     # success / failed / cancelled
)

NODE_DURATION = Histogram(
    "athena_node_duration_seconds",
    "节点执行耗时",
    ["node_name"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120],
)

LLM_TOKENS = Counter(
    "athena_llm_tokens_total",
    "LLM token 消耗",
    ["model", "type"],                              # input / output
)

LLM_COST_USD = Counter(
    "athena_llm_cost_usd_total",
    "LLM 累计成本(美元)",
    ["model"],
)

ACTIVE_TASKS = Gauge(
    "athena_active_tasks",
    "当前正在运行的任务数",
)

INTERRUPT_TIMEOUTS = Counter(
    "athena_interrupt_timeouts_total",
    "HITL 超时自动降级次数",
    ["interrupt_type"],
)


# ===================== 装饰器:给节点自动打指标 =====================
def trace_node(name: str) -> Callable:
    """装饰节点函数,自动记录执行时间。"""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return await fn(*args, **kwargs)
            finally:
                NODE_DURATION.labels(node_name=name).observe(time.perf_counter() - t0)
        
        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                NODE_DURATION.labels(node_name=name).observe(time.perf_counter() - t0)
        
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper
    return decorator


def setup_metrics() -> None:
    """启动时调用,把 /metrics 端点装到 FastAPI。"""
    from prometheus_client import make_asgi_app
    # 在 main.py 里 app.mount("/metrics", make_asgi_app())