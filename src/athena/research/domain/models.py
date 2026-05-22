"""Research OS domain models.

Pydantic models describing the structured research assets produced by the
system: projects, papers, notes, claims, evidence, taxonomies, baselines,
ideas and experiments. Fields follow `docs/RESEARCH_OS_ROADMAP.md` section 5
and `docs/RESEARCH_OS_IMPLEMENTATION_PLAN.md` section 3.2.

Convention: identity (`id`) and timestamp fields are auto-generated;
collections default to empty; status fields carry a sensible initial enum;
core semantic fields with no meaningful default are required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from .enums import (
    CheckpointStatus,
    CheckpointType,
    PaperScreeningStatus,
    ProjectStatus,
    ReviewDecision,
    SelectionStatus,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class ResearchProject(BaseModel):
    """A computer-science research task and its workspace."""

    id: str = Field(default_factory=lambda: _id("proj"))
    title: str
    research_question: str
    field: str | None = None
    constraints: list[str] = Field(default_factory=list)
    target_venue: str | None = None
    status: ProjectStatus = ProjectStatus.draft
    owner: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Paper(BaseModel):
    """A paper in a project's literature library."""

    id: str = Field(default_factory=lambda: _id("paper"))
    project_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    arxiv_id: str | None = None
    doi: str | None = None
    semantic_scholar_id: str | None = None
    citation_count: int | None = None
    code_url: str | None = None
    dataset_mentions: list[str] = Field(default_factory=list)
    screening_status: PaperScreeningStatus = PaperScreeningStatus.candidate
    relevance_score: float | None = None
    created_at: datetime = Field(default_factory=utcnow)


class PaperNote(BaseModel):
    """A structured reading note for a paper."""

    id: str = Field(default_factory=lambda: _id("note"))
    paper_id: str
    problem: str | None = None
    method: str | None = None
    training_setup: str | None = None
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    baselines: list[str] = Field(default_factory=list)
    main_results: str | None = None
    limitations: str | None = None
    reproducibility_notes: str | None = None
    important_sections: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class Claim(BaseModel):
    """A verifiable conclusion extracted from a paper or the research process."""

    id: str = Field(default_factory=lambda: _id("claim"))
    project_id: str
    text: str
    claim_type: str
    paper_id: str | None = None
    section: str | None = None
    confidence: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    status: str = "draft"
    created_at: datetime = Field(default_factory=utcnow)


class Evidence(BaseModel):
    """Evidence supporting a claim — the system's traceability anchor."""

    id: str = Field(default_factory=lambda: _id("ev"))
    claim_id: str
    source_type: str
    source_url: str | None = None
    paper_id: str | None = None
    section: str | None = None
    quote: str | None = None
    normalized_text: str | None = None
    confidence: float | None = None
    verification_status: str = "unchecked"
    created_at: datetime = Field(default_factory=utcnow)


class MethodTaxonomy(BaseModel):
    """A technical taxonomy: method families, their relations and open problems."""

    id: str = Field(default_factory=lambda: _id("tax"))
    project_id: str
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    summary: str | None = None
    open_problems: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class BaselineCandidate(BaseModel):
    """A reproducible baseline candidate."""

    id: str = Field(default_factory=lambda: _id("base"))
    project_id: str
    name: str
    method_summary: str
    paper_id: str | None = None
    code_url: str | None = None
    dataset: str | None = None
    metric: str | None = None
    reported_score: str | None = None
    reproduction_difficulty: str | None = None
    hardware_requirement: str | None = None
    expected_runtime: str | None = None
    license: str | None = None
    rank_score: float | None = None
    selection_reason: str | None = None
    status: str = "candidate"
    created_at: datetime = Field(default_factory=utcnow)


class Benchmark(BaseModel):
    """A candidate evaluation benchmark — a dataset paired with its metrics.

    Benchmarks are derived from the paper library: `adoption_count` is how many
    project papers evaluate on the dataset, which is the signal for how
    standard / comparable the benchmark is.
    """

    id: str = Field(default_factory=lambda: _id("bench"))
    project_id: str
    name: str
    dataset: str
    metrics: list[str] = Field(default_factory=list)
    task: str | None = None
    source_paper_ids: list[str] = Field(default_factory=list)
    adoption_count: int = 0
    status: SelectionStatus = SelectionStatus.candidate
    selection_reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class ResearchIdea(BaseModel):
    """A candidate research idea with multi-axis scoring."""

    id: str = Field(default_factory=lambda: _id("idea"))
    project_id: str
    title: str
    motivation: str
    core_hypothesis: str
    method_sketch: str
    expected_advantage: str | None = None
    required_baselines: list[str] = Field(default_factory=list)
    required_datasets: list[str] = Field(default_factory=list)
    evaluation_plan: str | None = None
    novelty_score: float | None = None
    feasibility_score: float | None = None
    risk_score: float | None = None
    overall_score: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    status: str = "candidate"
    created_at: datetime = Field(default_factory=utcnow)


class ExperimentSpec(BaseModel):
    """An experiment design for a baseline or proposed method."""

    id: str = Field(default_factory=lambda: _id("exp"))
    project_id: str
    task: str
    idea_id: str | None = None
    baseline_id: str | None = None
    dataset: str | None = None
    metrics: list[str] = Field(default_factory=list)
    train_command: str | None = None
    eval_command: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    expected_outputs: list[str] = Field(default_factory=list)
    hardware_requirement: str | None = None
    seed_plan: list[int] = Field(default_factory=list)
    ablation_plan: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class ExperimentRun(BaseModel):
    """A single execution of an experiment spec."""

    id: str = Field(default_factory=lambda: _id("run"))
    experiment_spec_id: str
    status: str = "pending"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    command: str | None = None
    exit_code: int | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    failure_reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class CodeArtifact(BaseModel):
    """A generated or collected code asset."""

    id: str = Field(default_factory=lambda: _id("code"))
    project_id: str
    path: str
    artifact_type: str = "code"
    language: str | None = None
    source: str | None = None
    related_baseline_id: str | None = None
    related_idea_id: str | None = None
    checksum: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class ReviewCheckpoint(BaseModel):
    """A human-in-the-loop checkpoint that blocks the runtime until decided.

    `status` tracks the lifecycle (pending -> decided); `decision` carries the
    human verdict once `status` is `decided`. Fields follow
    `docs/RESEARCH_OS_IMPLEMENTATION_PLAN.md` section 5.2.
    """

    id: str = Field(default_factory=lambda: _id("ckpt"))
    task_id: str
    project_id: str
    checkpoint_type: CheckpointType
    title: str
    content: dict[str, Any] = Field(default_factory=dict)
    status: CheckpointStatus = CheckpointStatus.pending
    decision: ReviewDecision | None = None
    comment: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    decided_at: datetime | None = None
