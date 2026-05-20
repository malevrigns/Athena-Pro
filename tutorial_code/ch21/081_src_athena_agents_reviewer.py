"""
Reviewer 综合所有信号,决定:写报告 / 补研究 / 强制通过。
"""
from __future__ import annotations
import logging
from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from pydantic import BaseModel, Field

from athena.config import get_settings
from athena.observability.costs import track_llm_cost
from athena.state.schemas import Phase, ResearchState

logger = logging.getLogger(__name__)
_settings = get_settings()


class ReviewDecision(BaseModel):
    approved: bool = Field(..., description="True=可写报告;False=需补研究")
    feedback: str = Field(..., description="简要说明:通过的赞许 / 不通过的具体改进方向")
    missing_aspects: list[str] = Field(
        default_factory=list,
        description="不通过时,列出缺失的研究方向(供 Planner 补研究)",
    )


REVIEWER_PROMPT_TEMPLATE = """你是严苛但公正的研究审稿员。

【用户原问题】
{question}

【研究成果概览】
共完成 {findings_count} 个子方向研究,信号汇总:
- 待核查的可疑陈述({disputed_count} 条):
{disputed_text}

- 引用问题({issues_count} 条):
{issues_text}

- 各方向研究小结:
{findings_text}

【你的任务】
判断是否可以让 Writer 写最终报告。

通过标准(满足以下全部即可通过):
✓ findings 覆盖了原问题的主要方面
✓ disputed 数 < findings 数的 30%
✓ citation issues 数 < findings 引用总数的 20%
✓ 没有明显的盲区

如果不通过,具体说明【缺失什么方向】(用于 Planner 补充)。

当前是第 {revision_round} 轮审稿(最多 {max_revisions} 轮)。
"""


async def reviewer_node(
    state: ResearchState,
) -> Command[Literal["writer", "planner"]]:
    settings = get_settings()
    findings = state.get("findings", [])
    disputed = state.get("disputed_claims", [])
    issues = state.get("citation_issues", [])
    revision_count = state.get("revision_count", 0)
    
    # 构造 Prompt
    findings_text = "\n".join(
        f"- [{f.topic_id}] {f.topic}: {f.summary[:200]}..."
        for f in findings
    )
    disputed_text = "\n".join(
        f"  • {c.text[:120]} ({c.verification_note})" for c in disputed[:10]
    ) or "  (无)"
    issues_text = "\n".join(f"  {i}" for i in issues[:10]) or "  (无)"
    
    prompt = REVIEWER_PROMPT_TEMPLATE.format(
        question=state["question"],
        findings_count=len(findings),
        disputed_count=len(disputed),
        disputed_text=disputed_text,
        issues_count=len(issues),
        issues_text=issues_text,
        findings_text=findings_text,
        revision_round=revision_count + 1,
        max_revisions=settings.graph.max_revision_count + 1,
    )
    
    llm = ChatOpenAI(
        model=settings.llm.primary_model,
        temperature=0,
    ).with_structured_output(ReviewDecision)
    
    with track_llm_cost(node="reviewer", model=settings.llm.primary_model):
        decision: ReviewDecision = await llm.ainvoke([
            {"role": "system", "content": prompt}
        ])
    
    # 强制通过:超过最大重试次数
    force_pass = revision_count >= settings.graph.max_revision_count
    
    if decision.approved or force_pass:
        status = "✓ 审稿通过" if decision.approved else "⚠️ 已达最大重试,强制通过"
        msg = HumanMessage(
            content=f"{status}\n反馈:{decision.feedback}",
            name="reviewer",
        )
        return Command(
            goto="writer",
            update={
                "phase": Phase.WRITING,
                "review_feedback": "",  # 清空
                "messages": [msg],
            },
        )
    
    # 打回:把 missing_aspects 串成 feedback 供 Planner
    feedback = decision.feedback + "\n\n建议补充方向:" + "; ".join(decision.missing_aspects)
    msg = HumanMessage(
        content=f"✗ 不通过(第 {revision_count + 1} 轮),反馈:\n{feedback}",
        name="reviewer",
    )
    return Command(
        goto="planner",
        update={
            "phase": Phase.PLANNING,
            "review_feedback": feedback,
            "revision_count": revision_count + 1,
            "messages": [msg],
        },
    )