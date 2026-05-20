from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException

from athena.api.agent_catalog import next_action_for, profile_for
from athena.api.agent_models import AgentItemSpec, AgentStatus, AgentTraceItem, AgentTraceResponse, AgentTraceSummary
from athena.runtime import runtime_store
from athena.schemas import Finding, ResearchTopic, StreamEvent, TaskStatus, TokenUsage
from athena.state import ResearchState


router = APIRouter(tags=["agents"])


@router.get("/v1/research/{task_id}/agents", response_model=AgentTraceResponse)
async def get_agent_trace(task_id: str) -> AgentTraceResponse:
    state = await runtime_store.get(task_id)
    if state is None:
        raise HTTPException(404, "task not found")
    return build_agent_trace(state)


def build_agent_trace(state: ResearchState) -> AgentTraceResponse:
    items = [
        _planner_item(state),
        _review_item(state),
        _supervisor_item(state),
        *_researcher_items(state),
        _quality_item(state),
        _reviewer_item(state),
        _writer_item(state),
    ]
    return AgentTraceResponse(items=items, summary=_summary(items, state.token_usage))


def _planner_item(state: ResearchState) -> AgentTraceItem:
    topics = state.plan.topics if state.plan else []
    output = f"已拆解 {len(topics)} 个研究主题" if topics else ""
    spec = AgentItemSpec(
        "planner", "planner", "Planner", _stage_status(state, bool(state.plan), TaskStatus.PLANNING),
        "把用户问题拆成可并行执行的研究计划", state.question, output, ["planner"], ["plan"])
    return _item(state, spec)


def _review_item(state: ResearchState) -> AgentTraceItem:
    decision = state.metadata.get("review_decision")
    done = bool(decision) or _is_after(state.status, TaskStatus.WAITING_REVIEW)
    output = "计划已进入执行阶段" if done else ""
    if decision:
        approved = bool(decision.get("approved"))
        output = f"审批结果: {'通过' if approved else '未通过'}"
        if decision.get("comments"):
            output += f"；{decision['comments']}"
    spec = AgentItemSpec(
        "plan_review", "review", "Plan Review", _stage_status(state, done, TaskStatus.WAITING_REVIEW),
        "在执行前确认计划、范围和人工审批结果", _plan_summary(state), output, ["plan_review"], ["review_approved"])
    return _item(state, spec)


def _supervisor_item(state: ResearchState) -> AgentTraceItem:
    routes = [e.payload.get("route", "") for e in state.events if e.type == "route"]
    output = " -> ".join([str(route) for route in routes if route]) or _research_summary(state)
    done = bool(state.findings) or state.final_report is not None
    spec = AgentItemSpec(
        "supervisor", "supervisor", "Supervisor", _stage_status(state, done, TaskStatus.RESEARCHING),
        "调度研究员、质量门和写作节点的下一步动作", _plan_summary(state), output, ["supervisor"], ["route"])
    return _item(state, spec)


def _researcher_items(state: ResearchState) -> list[AgentTraceItem]:
    topics = state.plan.topics if state.plan else []
    if not topics:
        return [_generic_researcher_item(state)]
    items = []
    for topic in topics:
        finding = _finding_for_topic(state, topic.id)
        items.append(_researcher_item(state, topic, finding))
    return items


def _generic_researcher_item(state: ResearchState) -> AgentTraceItem:
    status = _stage_status(state, bool(state.findings), TaskStatus.RESEARCHING)
    spec = AgentItemSpec(
        "researcher", "researcher", "Researcher Pool", status,
        "并行检索知识库和外部来源", state.question, _research_summary(state), ["researcher"], ["finding"])
    return _item(state, spec)


def _researcher_item(state: ResearchState, topic: ResearchTopic, finding: Finding | None) -> AgentTraceItem:
    source_count = len(finding.sources) if finding else 0
    knowledge_hits = _knowledge_hits(finding)
    output = _finding_summary(finding)
    status = _researcher_status(state, finding)
    spec = AgentItemSpec(
        f"researcher:{topic.id}", "researcher", topic.title, status,
        "先查内部知识库，再补充 Web / Paper / News 来源", topic.question, output, ["researcher"], ["finding"])
    item = _item(state, spec)
    item.evidence_count = len(finding.evidence) if finding else 0
    item.source_count = source_count
    item.knowledge_hits = knowledge_hits
    return item


def _quality_item(state: ResearchState) -> AgentTraceItem:
    output = ""
    if state.quality:
        output = f"overall={state.quality.overall:.2f}；sources={_total_sources(state)}"
    spec = AgentItemSpec(
        "quality_gate", "quality", "Quality Gate", _stage_status(state, bool(state.quality), TaskStatus.QUALITY_GATE),
        "校验事实性、覆盖度、引用完整性和矛盾风险", _research_summary(state), output, ["quality"], ["quality"])
    return _item(state, spec)


def _reviewer_item(state: ResearchState) -> AgentTraceItem:
    review = _last_event_payload_text(state, "review", "review")
    status: AgentStatus = "done" if review else "skipped" if state.quality else "queued"
    spec = AgentItemSpec(
        "reviewer", "reviewer", "Reviewer", status,
        "质量不足时提出补充研究建议并触发回路", _quality_summary(state), review, ["reviewer"], ["review"])
    item = _item(state, spec)
    return item


def _writer_item(state: ResearchState) -> AgentTraceItem:
    output = state.final_report.title if state.final_report else ""
    spec = AgentItemSpec(
        "writer", "writer", "Writer", _stage_status(state, bool(state.final_report), TaskStatus.WRITING),
        "把 finding、质量结果和引用合成为最终报告", _research_summary(state), output, ["writer"], ["done"])
    return _item(state, spec)


def _item(state: ResearchState, spec: AgentItemSpec) -> AgentTraceItem:
    usage = _usage_for(state.token_usage, spec.role)
    profile = profile_for(spec.role)
    return AgentTraceItem(
        id=spec.id, role=spec.role, title=spec.title, status=spec.status, objective=spec.objective,
        input_summary=spec.input_summary, output_summary=spec.output_summary,
        token_count=usage["tokens"], cost_usd=usage["cost"],
        autonomy_level=profile.autonomy_level,
        capabilities=list(profile.capabilities),
        tools=list(profile.tools),
        next_action=next_action_for(spec.role, spec.status),
        updated_at=_last_updated(state.events, spec.nodes, spec.event_types),
    )


def _stage_status(state: ResearchState, done: bool, active: TaskStatus) -> AgentStatus:
    if state.status == TaskStatus.FAILED:
        return "failed"
    if done:
        return "done"
    if state.status == active:
        return "running"
    if _is_after(state.status, active):
        return "skipped"
    return "queued"


def _researcher_status(state: ResearchState, finding: Finding | None) -> AgentStatus:
    if state.status == TaskStatus.FAILED:
        return "failed"
    if finding:
        return "done"
    if state.status == TaskStatus.RESEARCHING:
        return "running"
    if _is_after(state.status, TaskStatus.RESEARCHING):
        return "skipped"
    return "queued"


def _is_after(status: TaskStatus, pivot: TaskStatus) -> bool:
    order = list(TaskStatus)
    return order.index(status) > order.index(pivot)


def _finding_for_topic(state: ResearchState, topic_id: str) -> Finding | None:
    return next((finding for finding in state.findings if finding.topic_id == topic_id), None)


def _knowledge_hits(finding: Finding | None) -> int:
    if finding is None:
        return 0
    return sum(1 for source in finding.sources if source.source_type == "internal")


def _total_sources(state: ResearchState) -> int:
    return sum(len(finding.sources) for finding in state.findings)


def _summary(items: list[AgentTraceItem], usages: list[TokenUsage]) -> AgentTraceSummary:
    counts = Counter(item.status for item in items)
    capabilities = {capability for item in items for capability in item.capabilities}
    tools = {tool for item in items for tool in item.tools}
    return AgentTraceSummary(
        total_agents=len(items), completed_agents=counts["done"], running_agents=counts["running"],
        queued_agents=counts["queued"], skipped_agents=counts["skipped"], failed_agents=counts["failed"],
        source_count=sum(item.source_count for item in items),
        knowledge_hits=sum(item.knowledge_hits for item in items),
        total_tokens=sum(usage.input_tokens + usage.output_tokens for usage in usages),
        total_cost_usd=round(sum(usage.cost_usd for usage in usages), 6),
        capability_count=len(capabilities),
        tool_count=len(tools),
    )


def _usage_for(usages: list[TokenUsage], role: str) -> dict[str, float]:
    role_usage = [usage for usage in usages if usage.node == role]
    return {
        "tokens": sum(usage.input_tokens + usage.output_tokens for usage in role_usage),
        "cost": round(sum(usage.cost_usd for usage in role_usage), 6),
    }


def _last_updated(events: list[StreamEvent], nodes: list[str], event_types: list[str]) -> str:
    node_set = set(nodes)
    type_set = set(event_types)
    for event in reversed(events):
        if event.node in node_set or event.type in type_set:
            return event.ts.isoformat()
    return ""


def _plan_summary(state: ResearchState) -> str:
    if not state.plan:
        return ""
    titles = "、".join(topic.title for topic in state.plan.topics[:3])
    return f"{len(state.plan.topics)} 个主题: {titles}"


def _research_summary(state: ResearchState) -> str:
    return f"{len(state.findings)} 个 finding，{_total_sources(state)} 个来源"


def _quality_summary(state: ResearchState) -> str:
    if not state.quality:
        return ""
    return f"overall={state.quality.overall:.2f}"


def _finding_summary(finding: Finding | None) -> str:
    if finding is None:
        return ""
    return f"{finding.title}: {finding.summary}"


def _last_event_payload_text(state: ResearchState, event_type: str, key: str) -> str:
    for event in reversed(state.events):
        if event.type == event_type and event.payload.get(key):
            return str(event.payload[key])
    return ""
