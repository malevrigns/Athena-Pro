"""Research OS project and trace endpoints."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field, HttpUrl

from athena.persistence import get_store
from athena.research.artifacts import PaperMatrix, build_paper_matrix, paper_matrix_to_csv
from athena.research.domain import Claim, Evidence, Paper, PaperNote, PaperScreeningStatus, ResearchProject
from athena.research.persistence import ResearchRepository
from athena.research.services import check_evidence_completeness
from athena.research.services import create_paper as create_research_paper
from athena.research.services import create_paper_note as create_research_paper_note
from athena.research.services import create_project as create_research_project
from athena.research.services import execute_tool_with_trace
from athena.research.services import get_project_tool_trace
from athena.research.services import get_tool_trace
from athena.research.services.evidence_audit import EvidenceAuditReport
from athena.research.tools import ToolResult, ToolRouter, ToolTraceItem
from athena.research.tools.citation_graph import build_citation_graph_tool
from athena.research.tools.evidence_tools import build_claim_extract_tool
from athena.research.tools.paper_reader import build_paper_reader_tool
from athena.research.tools.paper_search import build_paper_search_tool


router = APIRouter(tags=["research-os"])


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


class PaperSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
    task_id: str | None = None


class ExtractPaperNoteRequest(BaseModel):
    task_id: str | None = None


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


class ClaimExtractRequest(BaseModel):
    task_id: str | None = None


class CitationGraphRequest(BaseModel):
    paper_id: str | None = None
    limit: int = Field(default=10, ge=1, le=50)
    task_id: str | None = None


async def _research_repo():
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


@router.post("/v1/projects", response_model=ResearchProject)
async def create_project(body: CreateProjectRequest):
    repo = await _research_repo()
    try:
        return await create_research_project(
            repo,
            title=body.title,
            research_question=body.research_question,
            field=body.field,
            constraints=body.constraints,
            target_venue=body.target_venue,
            owner=body.owner,
        )
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


@router.post("/v1/projects/{project_id}/papers", response_model=Paper)
async def create_paper(project_id: str, body: CreatePaperRequest):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    try:
        return await create_research_paper(
            repo,
            project_id=project_id,
            title=body.title,
            authors=body.authors,
            year=body.year,
            venue=body.venue,
            abstract=body.abstract,
            url=str(body.url) if body.url else None,
            pdf_url=str(body.pdf_url) if body.pdf_url else None,
            arxiv_id=body.arxiv_id,
            doi=body.doi,
            semantic_scholar_id=body.semantic_scholar_id,
            citation_count=body.citation_count,
            code_url=str(body.code_url) if body.code_url else None,
            dataset_mentions=body.dataset_mentions,
            screening_status=body.screening_status,
            relevance_score=body.relevance_score,
        )
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
    return await repo.list_project_papers(
        project_id,
        limit=limit,
        screening_status=screening_status,
    )


@router.get("/v1/projects/{project_id}/papers/{paper_id}", response_model=Paper)
async def get_paper(project_id: str, paper_id: str):
    repo = await _research_repo()
    return await _get_paper_or_404(repo, project_id, paper_id)


@router.post("/v1/projects/{project_id}/papers/{paper_id}/notes", response_model=PaperNote)
async def create_paper_note(project_id: str, paper_id: str, body: CreatePaperNoteRequest):
    repo = await _research_repo()
    await _get_paper_or_404(repo, project_id, paper_id)
    try:
        return await create_research_paper_note(
            repo,
            paper_id=paper_id,
            problem=body.problem,
            method=body.method,
            training_setup=body.training_setup,
            datasets=body.datasets,
            metrics=body.metrics,
            baselines=body.baselines,
            main_results=body.main_results,
            limitations=body.limitations,
            reproducibility_notes=body.reproducibility_notes,
            important_sections=body.important_sections,
        )
    except aiosqlite.IntegrityError as exc:
        raise HTTPException(409, "paper note already exists") from exc


@router.get("/v1/projects/{project_id}/papers/{paper_id}/notes", response_model=list[PaperNote])
async def list_paper_notes(project_id: str, paper_id: str):
    repo = await _research_repo()
    await _get_paper_or_404(repo, project_id, paper_id)
    return await repo.list_paper_notes(paper_id)


@router.post("/v1/projects/{project_id}/papers/{paper_id}/note-extract", response_model=ToolResult)
async def extract_paper_note(project_id: str, paper_id: str, body: ExtractPaperNoteRequest):
    repo = await _research_repo()
    await _get_paper_or_404(repo, project_id, paper_id)
    router = ToolRouter([build_paper_reader_tool(repo)])
    return await execute_tool_with_trace(
        repo,
        router,
        task_id=body.task_id or project_id,
        project_id=project_id,
        tool_name="paper_reader",
        arguments={"project_id": project_id, "paper_id": paper_id},
    )


@router.post("/v1/projects/{project_id}/paper-search", response_model=ToolResult)
async def search_project_papers(project_id: str, body: PaperSearchRequest):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    router = ToolRouter([build_paper_search_tool(repo)])
    return await execute_tool_with_trace(
        repo,
        router,
        task_id=body.task_id or project_id,
        project_id=project_id,
        tool_name="paper_search",
        arguments={"project_id": project_id, "query": body.query, "limit": body.limit},
    )


@router.post(
    "/v1/projects/{project_id}/papers/{paper_id}/claim-extract",
    response_model=ToolResult,
)
async def extract_paper_claims(project_id: str, paper_id: str, body: ClaimExtractRequest):
    repo = await _research_repo()
    await _get_paper_or_404(repo, project_id, paper_id)
    tool_router = ToolRouter([build_claim_extract_tool(repo)])
    return await execute_tool_with_trace(
        repo,
        tool_router,
        task_id=body.task_id or project_id,
        project_id=project_id,
        tool_name="claim_extract",
        arguments={"project_id": project_id, "paper_id": paper_id},
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
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    tool_router = ToolRouter([build_citation_graph_tool(repo)])
    return await execute_tool_with_trace(
        repo,
        tool_router,
        task_id=body.task_id or project_id,
        project_id=project_id,
        tool_name="citation_graph",
        arguments={"project_id": project_id, "paper_id": body.paper_id, "limit": body.limit},
    )


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


@router.get("/v1/projects/{project_id}/trace", response_model=list[ToolTraceItem])
async def get_project_trace(project_id: str):
    repo = await _research_repo()
    await _get_project_or_404(repo, project_id)
    return await get_project_tool_trace(repo, project_id)


@router.get("/v1/research/{task_id}/trace", response_model=list[ToolTraceItem])
async def get_research_trace(task_id: str):
    repo = await _research_repo()
    return await get_tool_trace(repo, task_id)
