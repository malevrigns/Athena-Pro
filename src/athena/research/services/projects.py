"""Project service helpers shared by API and future runtimes."""

from __future__ import annotations

from athena.research.domain import (
    Paper,
    PaperNote,
    PaperScreeningStatus,
    ProjectStatus,
    ResearchProject,
)
from athena.research.persistence import ResearchRepository
from athena.research.tools import ToolCallRecord, ToolTraceItem


async def create_project(
    repository: ResearchRepository,
    *,
    title: str,
    research_question: str,
    field: str | None = None,
    constraints: list[str] | None = None,
    target_venue: str | None = None,
    owner: str | None = None,
) -> ResearchProject:
    project = ResearchProject(
        title=title,
        research_question=research_question,
        field=field,
        constraints=list(constraints or []),
        target_venue=target_venue,
        owner=owner,
        status=ProjectStatus.draft,
    )
    await repository.create_project(project)
    return project


async def create_paper(
    repository: ResearchRepository,
    *,
    project_id: str,
    title: str,
    authors: list[str] | None = None,
    year: int | None = None,
    venue: str | None = None,
    abstract: str | None = None,
    url: str | None = None,
    pdf_url: str | None = None,
    arxiv_id: str | None = None,
    doi: str | None = None,
    semantic_scholar_id: str | None = None,
    citation_count: int | None = None,
    code_url: str | None = None,
    dataset_mentions: list[str] | None = None,
    screening_status: PaperScreeningStatus = PaperScreeningStatus.candidate,
    relevance_score: float | None = None,
) -> Paper:
    paper = Paper(
        project_id=project_id,
        title=title,
        authors=list(authors or []),
        year=year,
        venue=venue,
        abstract=abstract,
        url=url,
        pdf_url=pdf_url,
        arxiv_id=arxiv_id,
        doi=doi,
        semantic_scholar_id=semantic_scholar_id,
        citation_count=citation_count,
        code_url=code_url,
        dataset_mentions=list(dataset_mentions or []),
        screening_status=screening_status,
        relevance_score=relevance_score,
    )
    await repository.create_paper(paper)
    return paper


async def create_paper_note(
    repository: ResearchRepository,
    *,
    paper_id: str,
    problem: str | None = None,
    method: str | None = None,
    training_setup: str | None = None,
    datasets: list[str] | None = None,
    metrics: list[str] | None = None,
    baselines: list[str] | None = None,
    main_results: str | None = None,
    limitations: str | None = None,
    reproducibility_notes: str | None = None,
    important_sections: list[str] | None = None,
) -> PaperNote:
    note = PaperNote(
        paper_id=paper_id,
        problem=problem,
        method=method,
        training_setup=training_setup,
        datasets=list(datasets or []),
        metrics=list(metrics or []),
        baselines=list(baselines or []),
        main_results=main_results,
        limitations=limitations,
        reproducibility_notes=reproducibility_notes,
        important_sections=list(important_sections or []),
    )
    await repository.create_paper_note(note)
    return note


async def get_tool_trace(repository: ResearchRepository, task_id: str) -> list[ToolTraceItem]:
    calls = await repository.list_tool_calls(task_id)
    return await _hydrate_trace(repository, calls)


async def get_project_tool_trace(
    repository: ResearchRepository,
    project_id: str,
) -> list[ToolTraceItem]:
    calls = await repository.list_project_tool_calls(project_id)
    return await _hydrate_trace(repository, calls)


async def _hydrate_trace(
    repository: ResearchRepository,
    calls: list[ToolCallRecord],
) -> list[ToolTraceItem]:
    observations = await repository.list_tool_observations_for_calls([call.id for call in calls])
    return [
        ToolTraceItem(
            call=call,
            observations=observations.get(call.id, []),
        )
        for call in calls
    ]
