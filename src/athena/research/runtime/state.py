"""Unified runtime research state (roadmap section 7.2).

`ResearchRuntimeState` is the single business-state object for a research run:
every asset the runtime touches lives here, not scattered through Markdown or
graph fields. The roadmap calls it `ResearchState`; it is named
`ResearchRuntimeState` here only to avoid colliding with the legacy task-level
`athena.state.ResearchState`.

The implementation plan (section 4.1) expects the LangGraph layer to carry just
a `runtime` envelope around this object — so this model is deliberately a plain
mutable aggregate with no orchestration logic of its own.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from athena.research.domain import (
    BaselineCandidate,
    Claim,
    Evidence,
    ExperimentRun,
    ExperimentSpec,
    MethodTaxonomy,
    Paper,
    PaperNote,
    ResearchIdea,
    ResearchProject,
    ReviewCheckpoint,
)
from athena.research.persistence import ResearchRepository

from .loop import AgentLoopResult, StepRecord


class ResearchRuntimeState(BaseModel):
    """All research assets for one run, aggregated in one mutable object."""

    project: ResearchProject | None = None
    plan: dict[str, Any] = Field(default_factory=dict)
    papers: list[Paper] = Field(default_factory=list)
    paper_notes: list[PaperNote] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    taxonomy: MethodTaxonomy | None = None
    baselines: list[BaselineCandidate] = Field(default_factory=list)
    ideas: list[ResearchIdea] = Field(default_factory=list)
    experiment_specs: list[ExperimentSpec] = Field(default_factory=list)
    experiment_runs: list[ExperimentRun] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    review_decisions: list[ReviewCheckpoint] = Field(default_factory=list)
    tool_trace: list[StepRecord] = Field(default_factory=list)

    def register_loop_result(self, result: AgentLoopResult) -> None:
        """Append the trace of a completed agent-loop run to the tool trace."""
        self.tool_trace.extend(result.steps)

    def asset_counts(self) -> dict[str, int]:
        """Per-asset counts — used for progress display and prompt context."""
        return {
            "papers": len(self.papers),
            "paper_notes": len(self.paper_notes),
            "claims": len(self.claims),
            "evidence": len(self.evidence),
            "baselines": len(self.baselines),
            "ideas": len(self.ideas),
            "experiment_specs": len(self.experiment_specs),
            "experiment_runs": len(self.experiment_runs),
            "tool_steps": len(self.tool_trace),
        }

    def summary(self) -> str:
        """A short one-line state summary suitable for appending to a prompt."""
        counts = self.asset_counts()
        title = self.project.title if self.project else "(no project)"
        body = ", ".join(f"{key}={value}" for key, value in counts.items())
        return f"project={title}; {body}"


async def load_runtime_state(
    repository: ResearchRepository,
    project_id: str,
) -> ResearchRuntimeState:
    """Hydrate runtime state from persisted assets.

    Loads what the persistence layer currently exposes — project, papers,
    notes, claims, evidence and decided checkpoints. Asset families whose
    repository accessors are not built yet (taxonomy, baselines, ideas,
    experiments) start empty rather than being faked.
    """
    project = await repository.get_project(project_id)
    if project is None:
        raise LookupError("project not found")

    papers = await repository.list_project_papers(project_id, limit=500)
    paper_notes: list[PaperNote] = []
    for paper in papers:
        paper_notes.extend(await repository.list_paper_notes(paper.id))

    checkpoints = await repository.list_project_checkpoints(project_id)
    decided = [c for c in checkpoints if c.decision is not None]

    return ResearchRuntimeState(
        project=project,
        papers=papers,
        paper_notes=paper_notes,
        claims=await repository.list_project_claims(project_id),
        evidence=await repository.list_project_evidence(project_id),
        review_decisions=decided,
    )
