"""Tests for baseline and benchmark selection (roadmap section 11.2)."""

from __future__ import annotations

import pytest

from athena.research.domain import BaselineCandidate, Benchmark, ResearchProject, SelectionStatus
from athena.research.services.selection import select_baseline, select_benchmark


@pytest.mark.asyncio
async def test_select_baseline_marks_status_and_records_reason(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    baseline = BaselineCandidate(project_id=project.id, name="DPR", method_summary="dense retrieval")
    await repo.create_baseline(baseline)

    selected = await select_baseline(
        repo, project_id=project.id, baseline_id=baseline.id, reason="best reproducibility"
    )

    assert selected.status == SelectionStatus.selected.value
    assert selected.selection_reason == "best reproducibility"
    stored = await repo.get_baseline(baseline.id)
    assert stored.status == SelectionStatus.selected.value


@pytest.mark.asyncio
async def test_select_benchmark_marks_status(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    benchmark = Benchmark(project_id=project.id, name="MMLU", dataset="MMLU", adoption_count=5)
    await repo.create_benchmark(benchmark)

    selected = await select_benchmark(
        repo, project_id=project.id, benchmark_id=benchmark.id, reason="most comparable"
    )

    assert selected.status is SelectionStatus.selected
    stored = await repo.get_benchmark(benchmark.id)
    assert stored.status is SelectionStatus.selected
    assert stored.selection_reason == "most comparable"


@pytest.mark.asyncio
async def test_selection_rejects_unknown_or_cross_project_ids(make_store):
    repo = await make_store().research_repository()
    project_a = ResearchProject(title="A", research_question="Q?")
    project_b = ResearchProject(title="B", research_question="Q?")
    await repo.create_project(project_a)
    await repo.create_project(project_b)
    baseline = BaselineCandidate(project_id=project_a.id, name="DPR", method_summary="m")
    await repo.create_baseline(baseline)

    with pytest.raises(LookupError):
        await select_baseline(repo, project_id=project_a.id, baseline_id="base_missing")
    # a baseline owned by project A cannot be selected under project B.
    with pytest.raises(LookupError):
        await select_baseline(repo, project_id=project_b.id, baseline_id=baseline.id)
    with pytest.raises(LookupError):
        await select_benchmark(repo, project_id=project_a.id, benchmark_id="bench_missing")
