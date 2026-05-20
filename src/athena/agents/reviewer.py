from __future__ import annotations

import re
from uuid import uuid4

from athena.costs import guard_budget, record_llm_call
from athena.llm_factory import get_llm
from athena.prompts import REVIEWER_PROMPT
from athena.schemas import ResearchTopic
from athena.state import ResearchState


def _findings_block(state: ResearchState) -> str:
    if not state.findings:
        return "(尚无 findings)"
    lines = []
    for f in state.findings:
        lines.append(f"- {f.title}: {f.summary[:240]} (sources={len(f.sources)})")
    return "\n".join(lines)


_SUGGESTION_PATTERN = re.compile(r"^[\-\*\d\.\s]*补充[::]\s*(.+)$")


def _parse_suggestions(text: str) -> list[str]:
    out: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _SUGGESTION_PATTERN.match(line)
        if m:
            suggestion = m.group(1).strip().rstrip("。.")
            if suggestion:
                out.append(suggestion[:160])
    return out[:3]


@guard_budget("reviewer")
async def reviewer_node(state: ResearchState) -> ResearchState:
    """Inspect findings, optionally append follow-up topics to the plan.

    The node is idempotent within a single quality iteration: it consumes the current findings,
    asks the LLM if more is needed, and appends new ResearchTopics for the researcher to pick up.
    """
    if not state.plan:
        return state
    llm = get_llm("reviewer")
    prompt = REVIEWER_PROMPT.render(question=state.question, findings_block=_findings_block(state))
    try:
        result = await llm.complete_full(prompt, node="reviewer")
        record_llm_call(state, result)
        text = result.text
    except Exception as exc:
        state.add_error(f"reviewer llm error: {exc}", node="reviewer")
        text = "OK"
    review_text = (text or "").strip()
    state.metadata["last_review"] = review_text[:2000]
    state.add_event("review", node="reviewer", review=review_text[:2000])
    if review_text.upper().startswith("OK"):
        return state
    suggestions = _parse_suggestions(review_text)
    new_topics: list[ResearchTopic] = []
    for s in suggestions:
        topic = ResearchTopic(
            id=f"topic_{uuid4().hex[:6]}",
            title=f"补充调研: {s[:60]}",
            question=s,
            rationale="reviewer 建议补充",
            search_queries=[s],
            priority=3,
        )
        new_topics.append(topic)
    if new_topics:
        state.plan.topics.extend(new_topics)
        state.add_event("plan_expanded", node="reviewer", new_topics=[t.model_dump(mode="json") for t in new_topics])
    return state
