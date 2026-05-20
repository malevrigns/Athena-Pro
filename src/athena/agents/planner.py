from __future__ import annotations

import json
import re

from athena.costs import guard_budget, record_llm_call
from athena.llm_factory import get_llm
from athena.prompts import PLANNER_PROMPT
from athena.schemas import ResearchPlan, ResearchTopic, TaskStatus
from athena.state import ResearchState


def _topic_templates(question: str) -> list[ResearchTopic]:
    base = question.strip().rstrip("?").rstrip("?")
    return [
        ResearchTopic(
            title="生态与主要参与者",
            question=f"{base} 的主要参与者、开源项目、商业产品分别有哪些?",
            rationale="先建立市场与技术生态全景,防止后续分析只盯单一框架。",
            search_queries=[f"{base} ecosystem 2026", f"{base} market landscape", f"{base} 主要厂商 开源"],
            priority=1,
        ),
        ResearchTopic(
            title="技术路线与系统架构",
            question=f"{base} 的关键技术路线、架构模式和工程难点是什么?",
            rationale="实战项目需要落到可实现的架构,不能只停留在概念层。",
            search_queries=[f"{base} architecture", f"{base} technical patterns", f"{base} 工程实践"],
            priority=1,
        ),
        ResearchTopic(
            title="企业落地与商业价值",
            question=f"{base} 在企业里的落地场景、ROI 与限制是什么?",
            rationale="研究报告需要能帮助产品和业务决策。",
            search_queries=[f"{base} enterprise adoption", f"{base} ROI use cases", f"{base} 行业案例"],
            priority=2,
        ),
        ResearchTopic(
            title="风险、治理与评估",
            question=f"{base} 的安全、成本、评估和治理风险有哪些?",
            rationale="Agent 产品必须覆盖权限、成本、质量和审计。",
            search_queries=[f"{base} evaluation safety cost", f"{base} governance", f"{base} 风险 合规"],
            priority=2,
        ),
    ]


def _parse_llm_topics(text: str) -> list[ResearchTopic] | None:
    """Best-effort JSON extraction.  Falls back to None on any failure so we use templates."""
    if not text:
        return None
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", candidate, re.S)
    if fenced:
        candidate = fenced.group(1)
    # Find the outermost JSON array
    match = re.search(r"\[\s*\{.*?\}\s*\]", candidate, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except Exception:
        return None
    if not isinstance(data, list):
        return None
    topics: list[ResearchTopic] = []
    for idx, item in enumerate(data[:6]):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        q = str(item.get("question") or item.get("query") or "").strip()
        if not title or not q:
            continue
        queries = item.get("search_queries") or item.get("queries") or []
        if isinstance(queries, str):
            queries = [queries]
        queries = [str(x) for x in queries][:5] or [q]
        topics.append(ResearchTopic(
            title=title[:120],
            question=q[:400],
            rationale=str(item.get("rationale") or "")[:400],
            search_queries=queries,
            priority=int(item.get("priority", 1 if idx < 2 else 2)),
        ))
    return topics or None


@guard_budget("planner")
async def planner_node(state: ResearchState) -> ResearchState:
    state.set_status(TaskStatus.PLANNING, node="planner")
    llm = get_llm("planner")
    prompt = PLANNER_PROMPT.render(question=state.question)
    summary = ""
    topics: list[ResearchTopic] = []
    try:
        result = await llm.complete_full(prompt, node="planner")
        record_llm_call(state, result)
        summary = result.text
        topics = _parse_llm_topics(summary) or []
    except Exception as exc:
        state.add_error(f"planner llm error: {exc}", node="planner")
    if not topics:
        topics = _topic_templates(state.question)
    state.plan = ResearchPlan(
        question=state.question,
        topics=topics,
        assumptions=["公开资料可能存在时间滞后,关键事实需要来源交叉验证。"],
        success_criteria=["覆盖关键维度", "最终报告引用可追溯", f"质量分不低于 {0.7}"],
        estimated_cost_usd=0.18,
    )
    state.metadata["planner_summary"] = summary
    state.add_event("plan", node="planner", plan=state.plan.model_dump(mode="json"), summary=summary[:1000])
    return state
