"""Tests for benchmark extraction and persistence (roadmap section 12.3)."""

from __future__ import annotations

import pytest

from athena.research.domain import Benchmark, Paper, PaperNote, ResearchProject, SelectionStatus
from athena.research.services.benchmarks import extract_benchmark_candidates


@pytest.mark.asyncio
async def test_benchmark_round_trips_and_lists_by_adoption(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    niche = Benchmark(project_id=project.id, name="Niche", dataset="Niche", adoption_count=1)
    popular = Benchmark(
        project_id=project.id,
        name="MMLU",
        dataset="MMLU",
        metrics=["accuracy"],
        adoption_count=9,
    )
    await repo.create_benchmark(niche)
    await repo.create_benchmark(popular)

    assert await repo.get_benchmark(popular.id) == popular
    # list is ranked by adoption, most-used first.
    assert [b.dataset for b in await repo.list_project_benchmarks(project.id)] == ["MMLU", "Niche"]


@pytest.mark.asyncio
async def test_extract_benchmark_candidates_aggregates_datasets(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    paper_a = Paper(project_id=project.id, title="A")
    paper_b = Paper(project_id=project.id, title="B")
    await repo.create_paper(paper_a)
    await repo.create_paper(paper_b)
    await repo.create_paper_note(
        PaperNote(paper_id=paper_a.id, datasets=["MMLU", "GSM8K"], metrics=["accuracy"])
    )
    await repo.create_paper_note(
        PaperNote(paper_id=paper_b.id, datasets=["MMLU"], metrics=["f1"])
    )

    created = await extract_benchmark_candidates(repo, project.id)

    by_dataset = {b.dataset: b for b in created}
    assert set(by_dataset) == {"MMLU", "GSM8K"}
    # MMLU is used by both papers; its metrics are the union of the two notes.
    assert by_dataset["MMLU"].adoption_count == 2
    assert by_dataset["MMLU"].metrics == ["accuracy", "f1"]
    assert by_dataset["GSM8K"].adoption_count == 1
    assert all(b.status is SelectionStatus.candidate for b in created)


@pytest.mark.asyncio
async def test_extract_benchmark_candidates_is_idempotent(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    paper = Paper(project_id=project.id, title="A", dataset_mentions=["ImageNet"])
    await repo.create_paper(paper)

    first = await extract_benchmark_candidates(repo, project.id)
    second = await extract_benchmark_candidates(repo, project.id)

    assert [b.dataset for b in first] == ["ImageNet"]
    assert second == []  # ImageNet already has a benchmark


@pytest.mark.asyncio
async def test_extract_benchmark_candidates_rejects_unknown_project(make_store):
    repo = await make_store().research_repository()
    with pytest.raises(LookupError):
        await extract_benchmark_candidates(repo, "proj_missing")
