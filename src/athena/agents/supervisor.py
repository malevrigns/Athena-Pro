from __future__ import annotations

from typing import Literal

from athena.schemas import TaskStatus
from athena.state import ResearchState

Route = Literal["plan_review", "researcher", "quality_gate", "reviewer", "writer", "done", "cancelled"]


def supervisor_route(state: ResearchState) -> Route:
    if state.status == TaskStatus.CANCELLED:
        return "cancelled"
    if state.plan is None:
        return "plan_review"
    if not state.findings:
        return "researcher"
    if state.quality is None:
        return "quality_gate"
    if state.final_report is None:
        return "writer"
    return "done"


async def supervisor_node(state: ResearchState) -> ResearchState:
    route = supervisor_route(state)
    iteration = state.metadata.get("research_iteration", 1)
    quality = state.quality.overall if state.quality else None
    state.add_event(
        "route",
        node="supervisor",
        route=route,
        iteration=iteration,
        quality=quality,
        topic_count=len(state.plan.topics) if state.plan else 0,
        finding_count=len(state.findings),
    )
    return state
