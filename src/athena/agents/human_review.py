from __future__ import annotations

from athena.schemas import ReviewDecision, TaskStatus
from athena.state import ResearchState


async def plan_review_node(state: ResearchState, decision: ReviewDecision | None = None) -> ResearchState:
    """Human-in-the-loop review.

    API calls can pass a decision. The default demo path auto-approves so the starter runs from the
    terminal without a browser interaction.
    """
    state.set_status(TaskStatus.WAITING_REVIEW, node="plan_review")
    if decision is None:
        decision = ReviewDecision(approved=True, comments="demo auto approval")
    state.metadata["review_decision"] = decision.model_dump(mode="json")
    if decision.revised_topics and state.plan:
        state.plan.topics = decision.revised_topics
    if not decision.approved:
        state.status = TaskStatus.CANCELLED
        state.add_event("cancelled", node="plan_review", reason=decision.comments)
    else:
        state.add_event("review_approved", node="plan_review", comments=decision.comments)
    return state
