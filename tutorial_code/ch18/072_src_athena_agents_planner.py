"""
Planner Agent:拆解用户问题。
"""
from __future__ import annotations
import uuid
from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from pydantic import BaseModel, Field

from athena.config import get_settings
from athena.observability.costs import track_llm_cost
from athena.prompts.planner import render_planner_prompt
from athena.state.schemas import Phase, ResearchState

_settings = get_settings()


# ============= 结构化输出 schema =============

class SubTopic(BaseModel):
    """单个子研究方向。"""
    id: str = Field(..., description="snake_case 标识符,唯一,如 'market_landscape'")
    topic: str = Field(..., description="中文一句话描述这个子方向")
    why: str = Field(..., description="为什么这个方向重要,一句话")


class ResearchPlan(BaseModel):
    """完整的研究计划。"""
    sub_topics: list[SubTopic] = Field(..., min_length=2, max_length=8)
    rationale: str = Field(..., description="拆解逻辑说明")


# ============= 节点实现 =============

async def planner_node(
    state: ResearchState,
) -> Command[Literal["human_review", "supervisor"]]:
    """生成或修订研究计划。
    
    首次进入:state['plan_revision'] == 0,生成全新计划。
    重试进入:有 review_feedback,基于反馈补充方向。
    """
    settings = get_settings()
    is_revision = state.get("plan_revision", 0) > 0
    
    # 渲染 Prompt
    if is_revision:
        completed = [t["topic"] for t in state.get("research_plan", [])]
        system_prompt = render_planner_prompt(
            min_topics=1,
            max_topics=3,
            revision_feedback=state.get("review_feedback", ""),
            completed_topics=completed,
        )
    else:
        system_prompt = render_planner_prompt(
            min_topics=4,
            max_topics=settings.graph.max_research_topics,
        )
    
    # 调用 LLM with structured output
    llm = ChatOpenAI(
        model=settings.llm.primary_model,
        temperature=0.3,   # 留一点创造性,但不要太发散
        timeout=settings.llm.request_timeout,
    )
    structured = llm.with_structured_output(ResearchPlan)
    
    with track_llm_cost(node="planner", model=settings.llm.primary_model) as tracker:
        plan: ResearchPlan = await structured.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["question"]},
        ])
    
    # 给每个 sub_topic 加 uuid 后缀,防止 LLM 出现重复 id
    plan_dicts = [
        {
            "id": f"{st.id}_{uuid.uuid4().hex[:6]}",
            "topic": st.topic,
            "why": st.why,
        }
        for st in plan.sub_topics
    ]
    
    # 如果是修订,新方向追加到已有计划后面;否则全替换
    if is_revision:
        plan_dicts = state.get("research_plan", []) + plan_dicts
    
    # 写回 state,路由到 human_review(首次)或直接 supervisor(修订)
    summary = (
        f"📋 计划 v{state.get('plan_revision', 0) + 1} 已生成({len(plan.sub_topics)} 个新方向):\n"
        + "\n".join(f"  • {st.topic}" for st in plan.sub_topics)
        + f"\n\n规划理由:{plan.rationale}"
    )
    msg = HumanMessage(content=summary, name="planner")
    
    next_node = "supervisor" if is_revision else "human_review"
    
    return Command(
        goto=next_node,
        update={
            "research_plan": plan_dicts,
            "plan_revision": state.get("plan_revision", 0) + 1,
            "phase": Phase.AWAITING_APPROVAL if not is_revision else Phase.RESEARCHING,
            "messages": [msg],
            "total_tokens": tracker.tokens,
            "total_cost_cny": tracker.cost_cny,
        },
    )