"""Plan Review · 让用户审核研究计划"""
from __future__ import annotations
from typing import Literal

from langchain_core.messages import HumanMessage
from langgraph.types import Command, interrupt

from athena.config import settings
from athena.graph.state import ResearchState
from athena.observability import logger
from athena.notify import send_review_notification


async def plan_review_node(
    state: ResearchState,
) -> Command[Literal["supervisor", "planner"]]:
    """
    暂停图执行,等用户在 UI 上批准研究计划。
    支持:批准 / 修改 / 拒绝 / 超时自动批准。
    """
    plan = state["research_plan"]
    user_id = state.get("user_id")
    
    # 先发通知(邮件 / 飞书 / Slack)
    if user_id:
        await send_review_notification(
            user_id=user_id,
            task_id=state.get("task_id"),
            plan=plan,
        )
    
    # interrupt 会保存状态并暂停。前端收到 SSE 事件后让用户点选项
    user_decision = interrupt({
        "ask": "plan_review",
        "plan": plan,
        "deadline_sec": settings.plan_review_timeout_sec,    # 600 = 10 分钟
        "default_on_timeout": "approve",
    })
    
    action = user_decision.get("action", "approve")
    logger.info("plan_review_decision", action=action, user_id=user_id)
    
    if action == "approve":
        return Command(
            goto="supervisor",
            update={"messages": [HumanMessage(
                content=f"✓ 用户批准研究计划({len(plan)} 个方向)",
                name="human",
            )]}
        )
    
    if action == "modify":
        new_plan = user_decision.get("modified_plan") or plan
        return Command(
            goto="supervisor",
            update={
                "research_plan": new_plan,
                "messages": [HumanMessage(
                    content=f"✏️ 用户修改了研究计划:{new_plan}",
                    name="human",
                )]
            }
        )
    
    # reject → 回到 planner 重做
    return Command(
        goto="planner",
        update={
            "review_feedback": user_decision.get("reason", "用户希望重新规划"),
            "messages": [HumanMessage(
                content="❌ 用户拒绝当前计划,要求重新规划",
                name="human",
            )]
        }
    )