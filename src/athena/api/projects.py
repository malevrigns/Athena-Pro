"""Research OS project and trace endpoints."""

from __future__ import annotations

from collections.abc import Callable

import aiosqlite
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field, HttpUrl

from athena.llm_factory import get_llm
from athena.persistence import get_store
from athena.research.artifacts import PaperMatrix, build_paper_matrix, paper_matrix_to_csv
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
    ReviewDecision,
)
from athena.research.persistence import ResearchRepository
from athena.research.runtime import (
    CheckpointService,
    LLMAgentBrain,
    LoopLimits,
    ResearchSession,
    SessionResult,
)
from athena.research.services import check_evidence_completeness
from athena.research.services import create_paper as create_research_paper
from athena.research.services import create_paper_note as create_research_paper_note
from athena.research.services import create_project as create_research_project
from athena.research.services import execute_tool_with_trace
from athena.research.services import get_project_tool_trace
from athena.research.services import get_tool_trace
from athena.research.services import select_baseline as select_project_baseline
from athena.research.services import select_benchmark as select_project_benchmark
from athena.research.services.evidence_audit import EvidenceAuditReport
from athena.research.tools import ToolResult, ToolRouter, ToolSpec, ToolTraceItem
from athena.research.tools.baseline_tools import build_baseline_extract_tool, build_baseline_rank_tool
from athena.research.tools.benchmark_tools import build_benchmark_extract_tool
from athena.research.tools.citation_graph import build_citation_graph_tool
from athena.research.tools.evidence_tools import build_claim_extract_tool
from athena.research.tools.idea_tools import build_idea_rank_tool
from athena.research.tools.paper_reader import build_paper_reader_tool
from athena.research.tools.paper_search import build_paper_search_tool
from athena.research.tools.registry import build_research_tool_router
from athena.research.tools.taxonomy_tools import build_taxonomy_tool

router = APIRouter(tags=["research-os"])

ToolBuilder = Callable[[ResearchRepository], ToolSpec]


# --- request bodies ------------------------------------------------------


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    research_question: str = Field(min_length=3, max_length=3000)
    field: str | None = None
    constraints: list[str] = Field(default_factory=list)
    target_venue: str | None = None
    owner: str | None = None


class CreatePaperRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1900, le=2100)
    venue: str | None = Field(default=None, max_length=200)
    abstract: str | None = Field(default=None, max_length=8000)
    url: HttpUrl | None = None
    pdf_url: HttpUrl | None = None
    arxiv_id: str | None = Field(default=None, max_length=80)
    doi: str | None = Field(default=None, max_length=200)
    semantic_scholar_id: str | None = Field(default=None, max_length=200)
    citation_count: int | None = Field(default=None, ge=0)
    code_url: HttpUrl | None = None
    dataset_mentions: list[str] = Field(default_factory=list)
    screening_status: PaperScreeningStatus = PaperScreeningStatus.candidate
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)


class CreatePaperNoteRequest(BaseModel):
    problem: str | None = Field(default=None, max_length=4000)
    method: str | None = Field(default=None, max_length=8000)
    training_setup: str | None = Field(default=None, max_length=8000)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    baselines: list[str] = Field(default_factory=list)
    main_results: str | None = Field(default=None, max_length=8000)
    limitations: str | None = Field(default=None, max_length=8000)
    reproducibility_notes: str | None = Field(default=None, max_length=8000)
    important_sections: list[str] = Field(default_factory=list)


class CreateBaselineRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    method_summary: str = Field(min_length=1, max_length=8000)
    paper_id: str | None = None
    code_url: HttpUrl | None = None
    dataset: str | None = Field(default=None, max_length=300)
    metric: str | None = Field(default=None, max_length=300)
    reported_score: str | None = Field(default=None, max_length=300)
    reproduction_difficulty: str | None = Field(default=None, max_length=120)
    hardware_requirement: str | None = Field(default=None, max_length=300)
    expected_runtime: str | None = Field(default=None, max_length=120)
    license: str | None = Field(default=None, max_length=120)


class CreateIdeaRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    motivation: str = Field(min_length=1, max_length=8000)
    core_hypothesis: str = Field(min_length=1, max_length=8000)
    method_sketch: str = Field(min_length=1, max_length=8000)
    expected_advantage: str | None = Field(default=None, max_length=8000)
    required_baselines: list[str] = Field(default_factory=list)
    required_datasets: list[str] = Field(default_factory=list)
    evaluation_plan: str | None = Field(default=None, max_length=8000)
    novelty_score: float | None = Field(default=None, ge=0.0, le=1.0)
    feasibility_score: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)


class PaperSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
    task_id: str | None = None


class CitationGraphRequest(BaseModel):
    paper_id: str | None = None
    limit: int = Field(default=10, ge=1, le=50)
    task_id: str | None = None


class BaselineRankRequest(BaseModel):
    goal: str = Field(default="", max_length=2000)
    task_id: str | None = None


class TaskRefRequest(BaseModel):
    """Body for a trace-recorded action that takes no input beyond the project."""

    task_id: str | None = None


class RunProjectRequest(BaseModel):
    goal: str | None = Field(default=None, max_length=3000)
    max_iterations: int = Field(default=12, ge=1, le=50)
    task_id: str | None = None


class ReviewDecisionRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=4000)


class SelectionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=4000)


# --- shared helpers ------------------------------------------------------


async def _research_repo() -> ResearchRepository:
    return await get_store().research_repository()


async def _get_project_or_404(repo: ResearchRepository, project_id: str) -> ResearchProject:
    project = await repo.get_project(project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return project


async def _get_paper_or_404(repo: ResearchRepository, project_id: str, paper_id: str) -> Paper:
    paper = await repo.get_paper(paper_id)
    if paper is None or paper.project_id != project_id:
        raise HTTPException(404, "paper not found")
    return paper


async def _run_project_tool(
    project_id: str,
    build_tool: ToolBuilder,
    arguments: dict | None = None,
    *,
    task_id: str | None = None,
    paper_id: str | None = None,
) -> ToolResult:
    """Validate the project (and paper, when given), then run one tool with trace.

    Every Research OS tool endpoint is the same shape — resolve the repo, 404
    if the scope is missing, wrap the tool in a router, execute with trace —
    so that shape lives here once instead of in each endpoint body.
    """
    repo = await _research_repo()
    if paper_id is None:
        await _get_project_or_404(repo, project_id)
    else:
        await _get_paper_or_404(repo, project_id, paper_id)
    tool = build_tool(repo)
    return await execute_tool_with_trace(
        repo,
        ToolRouter([tool]),
        task_id=task_id or project_id,
        project_id=project_id,
        tool_name=tool.name,
        arguments={"project_id": project_id, **(arguments or {})},
    )


# --- projects ------------------------------------------------------------


@router.post("/v1/projects", response_model=ResearchProject)
async def create_project(body: CreateProjectRequest):
    repo = await _research_repo()
    try:
        return await create_research_project(repo, **body.model_dump())
    except aiosqlite.IntegrityError as exc:
        raise HTTPException(409, "project already exists") from exc


@router.get("/v1/projects", response_model=list[ResearchProject])
async def list_projects(limit: int = Query(50, ge=1, le=200)):
    repo = await _research_repo()
    return await repo.list_projects(limit=limit)


@router.get("/v1/projects/{project_id}", response_model=ResearchProject)
async def get_project(project_id: str):
    repo = await _research_repo()
    return await _get_project_or_404(repo, project_id)


@router.post("/v1/projects/{project_id}/runs", response_model=SessionResult)
async def run_project(project_id: str, body: RunProjectRequest):
    """Run the project through the Research OS agent runtime.

    This is the orchestration seam: a ResearchSession drives an LLM-backed
    AgentLoop over the full research toolset, instead of a fixed pipeline. The
    legacy `/api/tasks` SSE graph stays untouched as documented legacy compat.
    """
    repo = await _research_repo()
    project = await _get_project_or_404(repo, project_id)
    session = ResearchSession(
        repository=repo,
        router=build_research_tool_router(repo),
        project=project,
        limits=LoopLimits(max_iterations=body.max_iterations),
        task_id=body.task_id,
    )
    return await session.run(
        brain=LLMAgentBrain(get_llm("researcher")),
        goal=body.goal or project.research_question,
    )


# --- papers --------------------------------------------------------------


@router.post("/v1/projects/{project_id}/papers", response_model=Paper)
async def create_paper(project_id: str, body: CreatePaperRequest):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    try:
        # mode="json" so HttpUrl fields arrive as plain strings.
        return await create_research_paper(repo, project_id=project_id, **body.model_dump(mode="json"))
    except aiosqlite.IntegrityError as exc:
        raise HTTPException(409, "paper already exists") from exc


@router.get("/v1/projects/{project_id}/papers", response_model=list[Paper])
async def list_papers(
    project_id: str,
    limit: int = Query(100, ge=1, le=500),
    screening_status: PaperScreeningStatus | None = None,
):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    return await repo.list_project_papers(project_id, limit=limit, screening_status=screening_status)


@router.get("/v1/projects/{project_id}/papers/{paper_id}", response_model=Paper)
async def get_paper(project_id: str, paper_id: str):
    repo = await _research_repo()
    return await _get_paper_or_404(repo, project_id, paper_id)


@router.post("/v1/projects/{project_id}/papers/{paper_id}/notes", response_model=PaperNote)
async def create_paper_note(project_id: str, paper_id: str, body: CreatePaperNoteRequest):
    repo = await _research_repo()
    await _get_paper_or_404(repo, project_id, paper_id)
    try:
        return await create_research_paper_note(repo, paper_id=paper_id, **body.model_dump())
    except aiosqlite.IntegrityError as exc:
        raise HTTPException(409, "paper note already exists") from exc


@router.get("/v1/projects/{project_id}/papers/{paper_id}/notes", response_model=list[PaperNote])
async def list_paper_notes(project_id: str, paper_id: str):
    repo = await _research_repo()
    await _get_paper_or_404(repo, project_id, paper_id)
    return await repo.list_paper_notes(paper_id)


@router.post("/v1/projects/{project_id}/papers/{paper_id}/note-extract", response_model=ToolResult)
async def extract_paper_note(project_id: str, paper_id: str, body: TaskRefRequest):
    return await _run_project_tool(
        project_id, build_paper_reader_tool, {"paper_id": paper_id},
        task_id=body.task_id, paper_id=paper_id,
    )


@router.post("/v1/projects/{project_id}/paper-search", response_model=ToolResult)
async def search_project_papers(project_id: str, body: PaperSearchRequest):
    return await _run_project_tool(
        project_id, build_paper_search_tool,
        {"query": body.query, "limit": body.limit}, task_id=body.task_id,
    )


# --- claims & evidence ---------------------------------------------------


@router.post(
    "/v1/projects/{project_id}/papers/{paper_id}/claim-extract", response_model=ToolResult
)
async def extract_paper_claims(project_id: str, paper_id: str, body: TaskRefRequest):
    return await _run_project_tool(
        project_id, build_claim_extract_tool, {"paper_id": paper_id},
        task_id=body.task_id, paper_id=paper_id,
    )


@router.get("/v1/projects/{project_id}/claims", response_model=list[Claim])
async def list_project_claims(
    project_id: str,
    paper_id: str | None = None,
    limit: int = Query(500, ge=1, le=2000),
):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    if paper_id is not None:
        await _get_paper_or_404(repo, project_id, paper_id)
        return await repo.list_paper_claims(paper_id)
    return await repo.list_project_claims(project_id, limit=limit)


@router.get("/v1/projects/{project_id}/evidence", response_model=list[Evidence])
async def list_project_evidence(project_id: str):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    return await repo.list_project_evidence(project_id)


@router.post("/v1/projects/{project_id}/evidence/audit", response_model=EvidenceAuditReport)
async def audit_project_evidence(project_id: str):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    return await check_evidence_completeness(repo, project_id)


@router.post("/v1/projects/{project_id}/citation-graph", response_model=ToolResult)
async def build_project_citation_graph(project_id: str, body: CitationGraphRequest):
    return await _run_project_tool(
        project_id, build_citation_graph_tool,
        {"paper_id": body.paper_id, "limit": body.limit}, task_id=body.task_id,
    )


# --- paper matrix --------------------------------------------------------


@router.get("/v1/projects/{project_id}/paper-matrix", response_model=PaperMatrix)
async def get_paper_matrix(project_id: str):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    return await build_paper_matrix(repo, project_id)


@router.get("/v1/projects/{project_id}/paper-matrix.csv")
async def export_paper_matrix_csv(project_id: str):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    matrix = await build_paper_matrix(repo, project_id)
    return Response(
        content=paper_matrix_to_csv(matrix),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="paper_matrix_{project_id}.csv"'},
    )


# --- trace ---------------------------------------------------------------


@router.get("/v1/projects/{project_id}/trace", response_model=list[ToolTraceItem])
async def get_project_trace(project_id: str):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    return await get_project_tool_trace(repo, project_id)


@router.get("/v1/research/{task_id}/trace", response_model=list[ToolTraceItem])
async def get_research_trace(task_id: str):
    repo = await _research_repo()
    return await get_tool_trace(repo, task_id)


# --- review checkpoints --------------------------------------------------
# A POST decision both persists the verdict and wakes any run blocked in
# CheckpointService.wait(), so the human-in-the-loop is real, not cosmetic.


@router.get("/v1/projects/{project_id}/reviews", response_model=list[ReviewCheckpoint])
async def list_project_reviews(project_id: str):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    return await CheckpointService(repo).list_for_project(project_id)


@router.get("/v1/research/reviews/{checkpoint_id}", response_model=ReviewCheckpoint)
async def get_review_checkpoint(checkpoint_id: str):
    repo = await _research_repo()
    checkpoint = await CheckpointService(repo).get(checkpoint_id)
    if checkpoint is None:
        raise HTTPException(404, "review checkpoint not found")
    return checkpoint


async def _resolve_review(checkpoint_id: str, decision: ReviewDecision, comment: str | None):
    repo = await _research_repo()
    try:
        return await CheckpointService(repo).resolve(checkpoint_id, decision, comment=comment)
    except KeyError as exc:
        raise HTTPException(404, "review checkpoint not found") from exc


@router.post("/v1/research/reviews/{checkpoint_id}/approve", response_model=ReviewCheckpoint)
async def approve_review(checkpoint_id: str, body: ReviewDecisionRequest):
    return await _resolve_review(checkpoint_id, ReviewDecision.approved, body.comment)


@router.post("/v1/research/reviews/{checkpoint_id}/request-changes", response_model=ReviewCheckpoint)
async def request_review_changes(checkpoint_id: str, body: ReviewDecisionRequest):
    return await _resolve_review(checkpoint_id, ReviewDecision.changes_requested, body.comment)


@router.post("/v1/research/reviews/{checkpoint_id}/reject", response_model=ReviewCheckpoint)
async def reject_review(checkpoint_id: str, body: ReviewDecisionRequest):
    return await _resolve_review(checkpoint_id, ReviewDecision.rejected, body.comment)


# --- Phase 5: taxonomy ---------------------------------------------------


@router.get("/v1/projects/{project_id}/taxonomy", response_model=MethodTaxonomy)
async def get_project_taxonomy(project_id: str):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    taxonomy = await repo.latest_project_taxonomy(project_id)
    if taxonomy is None:
        raise HTTPException(404, "no taxonomy has been built for this project")
    return taxonomy


@router.post("/v1/projects/{project_id}/taxonomy/build", response_model=ToolResult)
async def build_project_taxonomy(project_id: str, body: TaskRefRequest):
    return await _run_project_tool(project_id, build_taxonomy_tool, task_id=body.task_id)


# --- Phase 5: baselines --------------------------------------------------


@router.get("/v1/projects/{project_id}/baselines", response_model=list[BaselineCandidate])
async def list_project_baselines(project_id: str):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    return await repo.list_project_baselines(project_id)


@router.post("/v1/projects/{project_id}/baselines", response_model=BaselineCandidate)
async def create_baseline(project_id: str, body: CreateBaselineRequest):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    baseline = BaselineCandidate(project_id=project_id, **body.model_dump(mode="json"))
    await repo.create_baseline(baseline)
    return baseline


@router.post("/v1/projects/{project_id}/baselines/extract", response_model=ToolResult)
async def extract_project_baselines(project_id: str, body: TaskRefRequest):
    return await _run_project_tool(project_id, build_baseline_extract_tool, task_id=body.task_id)


@router.post("/v1/projects/{project_id}/baselines/rank", response_model=ToolResult)
async def rank_project_baselines(project_id: str, body: BaselineRankRequest):
    return await _run_project_tool(
        project_id, build_baseline_rank_tool, {"goal": body.goal}, task_id=body.task_id,
    )


@router.post(
    "/v1/projects/{project_id}/baselines/{baseline_id}/select", response_model=BaselineCandidate
)
async def select_baseline(project_id: str, baseline_id: str, body: SelectionRequest):
    """Human-only: mark a baseline as selected (not exposed as an agent tool)."""
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    try:
        return await select_project_baseline(
            repo, project_id=project_id, baseline_id=baseline_id, reason=body.reason
        )
    except LookupError as exc:
        raise HTTPException(404, "baseline not found") from exc


# --- Phase 5: ideas ------------------------------------------------------


@router.get("/v1/projects/{project_id}/ideas", response_model=list[ResearchIdea])
async def list_project_ideas(project_id: str):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    return await repo.list_project_ideas(project_id)


@router.post("/v1/projects/{project_id}/ideas", response_model=ResearchIdea)
async def create_idea(project_id: str, body: CreateIdeaRequest):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    idea = ResearchIdea(project_id=project_id, **body.model_dump())
    await repo.create_idea(idea)
    return idea


@router.post("/v1/projects/{project_id}/ideas/rank", response_model=ToolResult)
async def rank_project_ideas(project_id: str, body: TaskRefRequest):
    return await _run_project_tool(project_id, build_idea_rank_tool, task_id=body.task_id)


# --- Phase 5: benchmarks -------------------------------------------------


@router.get("/v1/projects/{project_id}/benchmarks", response_model=list[Benchmark])
async def list_project_benchmarks(project_id: str):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    return await repo.list_project_benchmarks(project_id)


@router.post("/v1/projects/{project_id}/benchmarks/extract", response_model=ToolResult)
async def extract_project_benchmarks(project_id: str, body: TaskRefRequest):
    return await _run_project_tool(project_id, build_benchmark_extract_tool, task_id=body.task_id)


@router.post("/v1/projects/{project_id}/benchmarks/{benchmark_id}/select", response_model=Benchmark)
async def select_benchmark(project_id: str, benchmark_id: str, body: SelectionRequest):
    """Human-only: mark a benchmark as selected (not exposed as an agent tool)."""
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    try:
        return await select_project_benchmark(
            repo, project_id=project_id, benchmark_id=benchmark_id, reason=body.reason
        )
    except LookupError as exc:
        raise HTTPException(404, "benchmark not found") from exc
