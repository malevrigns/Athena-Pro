from __future__ import annotations

from athena.agents.citation_validator import validate_findings_sources
from athena.agents.fact_checker import FactChecker
from athena.schemas import TaskStatus
from athena.state import ResearchState


async def quality_gate_node(state: ResearchState) -> ResearchState:
    """Deterministic check — no LLM call, so no usage record is needed."""
    state.set_status(TaskStatus.QUALITY_GATE, node="quality_gate")
    state.findings, citation_errors = validate_findings_sources(state.findings)
    checker = FactChecker()
    state.quality = checker.score(state.findings)
    for error in citation_errors:
        state.add_error(error, node="citation_validator")
    state.add_event("quality", node="quality_gate", quality=state.quality.model_dump(mode="json"))
    if state.quality.overall < 0.55:
        state.add_error("quality gate failed: overall score below threshold", node="quality_gate")
    return state
