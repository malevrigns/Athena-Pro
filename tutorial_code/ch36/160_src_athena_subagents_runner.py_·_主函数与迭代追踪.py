"""跑一个 subagent 直到结束 / 超出迭代上限"""
from __future__ import annotations
import asyncio
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from athena.observability import logger
from athena.costs import get_current_ledger


async def run_isolated(
    sub_graph,
    task: str,
    max_iterations: int = 10,
    timeout_sec: float = 60.0,
) -> str:
    """
    在隔离上下文里跑 subagent,返回 LLM 最后的输出。
    关键:
      - 没有 checkpointer,subagent 是无状态的(运行完就丢)
      - max_iterations 限制 LLM 调用次数,防止失控
      - 单次超时 60s,超了强制终止
      - 成本归到当前 ledger(主 task 承担)
    """
    config = {
        "recursion_limit": max_iterations * 2,    # 每次迭代约 2 步(llm + tool)
    }
    initial_state = {
        "messages": [HumanMessage(content=task)],
    }
    
    iterations = 0
    last_ai_msg: AIMessage | None = None
    
    async def _run():
        nonlocal iterations, last_ai_msg
        async for chunk in sub_graph.astream(initial_state, config=config,
                                              stream_mode="updates"):
            for node, update in chunk.items():
                if msgs := update.get("messages"):
                    for msg in msgs:
                        if isinstance(msg, AIMessage):
                            last_ai_msg = msg
                            iterations += 1
                            if iterations >= max_iterations:
                                logger.warning(
                                    "subagent_iter_limit",
                                    iterations=iterations,
                                )
                                return                # 跳出 astream 循环