"""
delegate_to_subagent 工具
让主 Agent 把任务"外包"给一个独立上下文的 subagent。
"""
from __future__ import annotations
from typing import Annotated, Literal
from langchain_core.tools import tool

from athena.subagents.registry import dispatch_subagent


@tool
async def delegate_to_subagent(
    agent_type: Annotated[
        Literal["web_researcher", "fact_checker", "code_runner", "doc_reader"],
        "要派出的 subagent 类型。每个类型有不同的工具集和系统提示。"
    ],
    task: Annotated[
        str,
        "给 subagent 的明确任务。一句话描述,subagent 看不到你这边的对话,所以要包含所有必要上下文。"
    ],
    max_iterations: Annotated[
        int,
        "subagent 最多跑几轮 LLM 调用,防止无限循环。建议 5-15。默认 10。"
    ] = 10,
) -> str:
    """
    把任务派给一个独立 subagent。Subagent 在隔离的上下文中工作,
    完成后返回精炼的结果字符串给你。
    
    使用场景:
    - 你需要做一个"调查",涉及多次工具调用,但只想要最终结论
    - 你想让一个"专家"角色处理特定子问题(代码执行 / 文档阅读)
    - 你的当前对话已经很长,继续往里塞内容效果会下降
    
    例子:
      delegate_to_subagent(
        agent_type="web_researcher",
        task="查清楚 2026 年 Q1 美国 CPI 同比涨幅,要求至少 2 个独立来源",
        max_iterations=8,
      )
    """
    result = await dispatch_subagent(
        agent_type=agent_type,
        task=task,
        max_iterations=max_iterations,
    )
    return result