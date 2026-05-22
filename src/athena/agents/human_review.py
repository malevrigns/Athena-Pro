from __future__ import annotations

import asyncio

from athena.config import get_settings
from athena.hitl import get_gate
from athena.observability import logger
from athena.schemas import ReviewDecision, TaskStatus
from athena.state import ResearchState


async def plan_review_request_node(state: ResearchState) -> ResearchState:
    """Park the task at plan review and signal the UI.

    The actual blocking wait lives in `plan_review_apply_node` — splitting the
    two means the `review_required` event is flushed to the SSE client before
    the graph blocks, so the reviewer can actually see the request.
    """
    # Idempotent: a resumed run that was already reviewed skips straight past.
    if state.metadata.get("review_decision"):
        return state
    state.set_status(TaskStatus.WAITING_REVIEW, node="plan_review")
    if get_gate(state.task_id) is not None:
        state.add_event(
            "review_required",
            node="plan_review",
            stage="plan",
            topic_count=len(state.plan.topics) if state.plan else 0,
            message="研究计划已生成,等待人工审批",
        )
    return state


async def plan_review_apply_node(
    state: ResearchState,
    decision: ReviewDecision | None = None,
) -> ResearchState:
    """Block for the human plan-review decision (if any), then apply it.

    Research only proceeds once the decision is in — this is the real
    human-in-the-loop gate, not an advisory note.
    """
    if decision is None:
        existing = state.metadata.get("review_decision")
        if existing:
            # Idempotent: a resumed run reuses the decision already made.
            decision = ReviewDecision.model_validate(existing)
        else:
            decision = await _resolve_decision(state)
    state.metadata["review_decision"] = decision.model_dump(mode="json")
    if decision.revised_topics and state.plan:
        state.plan.topics = decision.revised_topics
    if not decision.approved:
        state.status = TaskStatus.CANCELLED
        state.add_event("cancelled", node="plan_review", reason=decision.comments or "计划被驳回")
    else:
        state.add_event("review_approved", node="plan_review", comments=decision.comments)
    return state


async def _resolve_decision(state: ResearchState) -> ReviewDecision:
    """Wait for a human decision when a reviewer gate is attached.

    No gate (CLI / tests / langgraph path) -> auto-approve so unattended runs
    still complete. The wait is bounded by `review_timeout_sec`; on timeout the
    plan is auto-approved rather than failing the task.
    """
    gate = get_gate(state.task_id)
    if gate is None:
        return ReviewDecision(approved=True, comments="自动批准(无人工审阅接入)")
    timeout = max(30, get_settings().review_timeout_sec)
    try:
        await asyncio.wait_for(gate.event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("plan_review.timeout task_id=%s timeout=%s", state.task_id, timeout)
        return ReviewDecision(approved=True, comments=f"审阅超时({timeout}s),自动批准")
    return gate.decision or ReviewDecision(approved=True, comments="收到空决策,自动批准")
