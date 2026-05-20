"""
Supervisor:中央调度。纯 Python,不调 LLM。
"""
from __future__ import annotations
from typing import Literal

from langchain_core.messages import HumanMessage
from langgraph.types import Command, Send

from athena.state.schemas import Phase, ResearchState


# Supervisor 可以路由到的目的地集合
SupervisorTarget = Literal[
    "researcher",
    "fact_checker_subgraph",
    "citation_validator_subgraph",
    "reviewer",
    "writer",
    "planner",   # 仅在 Reviewer 打回后才会出现
]


async def supervisor_node(
    state: ResearchState,
) -> Command[SupervisorTarget]:
    """根据当前 state 决定下一步派谁。"""
    phase = state.get("phase", Phase.PLANNING)
    plan = state.get("research_plan", [])
    findings = state.get("findings", [])
    
    completed_ids = {f.topic_id for f in findings}
    pending = [t for t in plan if t["id"] not in completed_ids]
    
    # ① 还有未研究的 → 并行派 Researcher
    if pending:
        msg = HumanMessage(
            content=f"🔀 派遣 {len(pending)} 个研究员并行调研:" +
                    ", ".join(t["topic"][:20] + "..." for t in pending[:3]),
            name="supervisor",
        )
        return Command(
            goto=[
                Send("researcher", {
                    "topic_id": t["id"],
                    "topic": t["topic"],
                    "why": t["why"],
                    "task_id": state["task_id"],
                })
                for t in pending
            ],
            update={
                "phase": Phase.RESEARCHING,
                "current_topic_ids": [t["id"] for t in pending],
                "messages": [msg],
            },
        )
    
    # ② 所有 topic 研究完了 → 进入质量门控
    # 还没做事实核查?
    if not state.get("disputed_claims") and phase != Phase.FACT_CHECKING:
        return Command(
            goto="fact_checker_subgraph",
            update={
                "phase": Phase.FACT_CHECKING,
                "messages": [HumanMessage(
                    content="🔍 进入事实核查阶段...",
                    name="supervisor",
                )],
            },
        )
    
    # 还没做引用验证?
    if not state.get("citation_issues") and phase != Phase.CITATION_VALIDATING:
        return Command(
            goto="citation_validator_subgraph",
            update={
                "phase": Phase.CITATION_VALIDATING,
                "messages": [HumanMessage(
                    content="📎 进入引用验证阶段...",
                    name="supervisor",
                )],
            },
        )
    
    # ③ 质量门控都做完了 → Reviewer 综合评审
    if phase != Phase.REVIEWING:
        return Command(
            goto="reviewer",
            update={
                "phase": Phase.REVIEWING,
                "messages": [HumanMessage(
                    content="📝 提交审稿...",
                    name="supervisor",
                )],
            },
        )
    
    # ④ 默认(理论不该到这里):去 Writer
    return Command(
        goto="writer",
        update={"phase": Phase.WRITING},
    )