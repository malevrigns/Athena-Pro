"""Persistence contract for Research OS domain assets.

This module defines the abstract interface only; concrete backends live
alongside it (see `sqlite_repository.py`). Phase 1 step 2 covers
`ResearchProject` persistence — later phases extend this contract to papers,
claims, evidence, baselines, ideas and experiments.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from athena.research.domain import (
    BaselineCandidate,
    Benchmark,
    Claim,
    Evidence,
    MethodTaxonomy,
    Paper,
    PaperNote,
    PaperScreeningStatus,
    ResearchIdea,
    ResearchProject,
    ReviewCheckpoint,
)
from athena.research.events import ResearchEvent
from athena.research.tools import ToolCallRecord, ToolObservationRecord


class ResearchRepository(ABC):
    """Durable storage for Research OS domain models."""

    @abstractmethod
    async def create_project(self, project: ResearchProject) -> None:
        """Insert a new project. Raises if a project with the same id exists."""

    @abstractmethod
    async def get_project(self, project_id: str) -> ResearchProject | None:
        """Return the project with `project_id`, or None if it does not exist."""

    @abstractmethod
    async def list_projects(self, limit: int = 50) -> list[ResearchProject]:
        """Return projects ordered by `updated_at` descending."""

    @abstractmethod
    async def upsert_project(self, project: ResearchProject) -> None:
        """Insert the project, or update it in place if its id already exists."""

    @abstractmethod
    async def create_paper(self, paper: Paper) -> None:
        """Insert a new paper. Raises if a paper with the same id exists."""

    @abstractmethod
    async def upsert_paper(self, paper: Paper) -> None:
        """Insert the paper, or update it in place if its id already exists."""

    @abstractmethod
    async def get_paper(self, paper_id: str) -> Paper | None:
        """Return the paper with `paper_id`, or None if it does not exist."""

    @abstractmethod
    async def list_project_papers(
        self,
        project_id: str,
        *,
        limit: int = 100,
        screening_status: PaperScreeningStatus | None = None,
    ) -> list[Paper]:
        """Return papers for a project ordered by creation time descending."""

    @abstractmethod
    async def create_paper_note(self, note: PaperNote) -> None:
        """Insert a structured reading note for a paper."""

    @abstractmethod
    async def upsert_paper_note(self, note: PaperNote) -> None:
        """Insert or update a structured reading note."""

    @abstractmethod
    async def get_paper_note(self, note_id: str) -> PaperNote | None:
        """Return a paper note, or None if it does not exist."""

    @abstractmethod
    async def list_paper_notes(self, paper_id: str) -> list[PaperNote]:
        """Return reading notes for a paper ordered by creation time descending."""

    @abstractmethod
    async def record_tool_call(self, call: ToolCallRecord) -> None:
        """Persist a tool call trace record."""

    @abstractmethod
    async def record_tool_observation(self, observation: ToolObservationRecord) -> None:
        """Persist a tool observation trace record."""

    @abstractmethod
    async def list_tool_calls(self, task_id: str) -> list[ToolCallRecord]:
        """Return tool calls for a task ordered by creation time."""

    @abstractmethod
    async def list_project_tool_calls(self, project_id: str) -> list[ToolCallRecord]:
        """Return tool calls for a project ordered by creation time."""

    @abstractmethod
    async def list_tool_observations(self, tool_call_id: str) -> list[ToolObservationRecord]:
        """Return observations for a tool call ordered by creation time."""

    @abstractmethod
    async def list_tool_observations_for_calls(
        self,
        tool_call_ids: list[str],
    ) -> dict[str, list[ToolObservationRecord]]:
        """Return observations grouped by tool call id."""

    @abstractmethod
    async def create_claim(self, claim: Claim) -> None:
        """Insert a new verifiable claim."""

    @abstractmethod
    async def upsert_claim(self, claim: Claim) -> None:
        """Insert the claim, or update it in place if its id already exists."""

    @abstractmethod
    async def get_claim(self, claim_id: str) -> Claim | None:
        """Return a claim, or None if it does not exist."""

    @abstractmethod
    async def list_project_claims(self, project_id: str, *, limit: int = 500) -> list[Claim]:
        """Return claims for a project ordered by creation time ascending."""

    @abstractmethod
    async def list_paper_claims(self, paper_id: str) -> list[Claim]:
        """Return claims extracted from one paper ordered by creation time."""

    @abstractmethod
    async def create_evidence(self, evidence: Evidence) -> None:
        """Insert a new evidence record supporting a claim."""

    @abstractmethod
    async def get_evidence(self, evidence_id: str) -> Evidence | None:
        """Return an evidence record, or None if it does not exist."""

    @abstractmethod
    async def list_claim_evidence(self, claim_id: str) -> list[Evidence]:
        """Return evidence records supporting a claim."""

    @abstractmethod
    async def list_project_evidence(self, project_id: str) -> list[Evidence]:
        """Return every evidence record whose claim belongs to a project."""

    @abstractmethod
    async def create_checkpoint(self, checkpoint: ReviewCheckpoint) -> None:
        """Insert a new human-in-the-loop review checkpoint."""

    @abstractmethod
    async def upsert_checkpoint(self, checkpoint: ReviewCheckpoint) -> None:
        """Insert the checkpoint, or update it in place if its id already exists."""

    @abstractmethod
    async def get_checkpoint(self, checkpoint_id: str) -> ReviewCheckpoint | None:
        """Return a review checkpoint, or None if it does not exist."""

    @abstractmethod
    async def list_project_checkpoints(self, project_id: str) -> list[ReviewCheckpoint]:
        """Return review checkpoints for a project ordered by creation time."""

    @abstractmethod
    async def record_research_event(self, event: ResearchEvent) -> None:
        """Persist a typed Research OS event to the durable event log."""

    @abstractmethod
    async def list_research_events(self, task_id: str) -> list[dict]:
        """Return persisted event payloads for a task ordered by sequence."""

    @abstractmethod
    async def create_taxonomy(self, taxonomy: MethodTaxonomy) -> None:
        """Insert a method taxonomy snapshot for a project."""

    @abstractmethod
    async def get_taxonomy(self, taxonomy_id: str) -> MethodTaxonomy | None:
        """Return a taxonomy snapshot, or None if it does not exist."""

    @abstractmethod
    async def latest_project_taxonomy(self, project_id: str) -> MethodTaxonomy | None:
        """Return the most recent taxonomy snapshot for a project."""

    @abstractmethod
    async def create_baseline(self, baseline: BaselineCandidate) -> None:
        """Insert a new baseline candidate."""

    @abstractmethod
    async def upsert_baseline(self, baseline: BaselineCandidate) -> None:
        """Insert the baseline, or update it in place if its id already exists."""

    @abstractmethod
    async def get_baseline(self, baseline_id: str) -> BaselineCandidate | None:
        """Return a baseline candidate, or None if it does not exist."""

    @abstractmethod
    async def list_project_baselines(self, project_id: str) -> list[BaselineCandidate]:
        """Return baseline candidates for a project ordered by creation time."""

    @abstractmethod
    async def create_idea(self, idea: ResearchIdea) -> None:
        """Insert a new research idea."""

    @abstractmethod
    async def upsert_idea(self, idea: ResearchIdea) -> None:
        """Insert the idea, or update it in place if its id already exists."""

    @abstractmethod
    async def get_idea(self, idea_id: str) -> ResearchIdea | None:
        """Return a research idea, or None if it does not exist."""

    @abstractmethod
    async def list_project_ideas(self, project_id: str) -> list[ResearchIdea]:
        """Return research ideas for a project ordered by creation time."""

    @abstractmethod
    async def create_benchmark(self, benchmark: Benchmark) -> None:
        """Insert a new benchmark candidate."""

    @abstractmethod
    async def upsert_benchmark(self, benchmark: Benchmark) -> None:
        """Insert the benchmark, or update it in place if its id already exists."""

    @abstractmethod
    async def get_benchmark(self, benchmark_id: str) -> Benchmark | None:
        """Return a benchmark, or None if it does not exist."""

    @abstractmethod
    async def list_project_benchmarks(self, project_id: str) -> list[Benchmark]:
        """Return a project's benchmarks ranked by adoption (most-used first)."""
