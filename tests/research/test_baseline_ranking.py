"""Tests for baseline extraction and multi-axis ranking (plan section 7.1)."""

from __future__ import annotations

import pytest

from athena.research.domain import BaselineCandidate, Paper, PaperNote, ResearchProject
from athena.research.services.baselines import (
    extract_baseline_candidates,
    rank_baselines,
    score_baseline,
)

_AXES = {
    "reported_strength",
    "code_availability",
    "dataset_availability",
    "implementation_complexity",
    "hardware_cost",
    "license_safety",
    "relevance_to_user_goal",
}


def test_score_baseline_keeps_every_axis_and_outranks_a_bare_candidate():
    strong = BaselineCandidate(
        project_id="p",
        name="strong baseline",
        method_summary="a well-supported method",
        code_url="https://github.com/example/strong",
        dataset="MMLU",
        reported_score="90.1 EM",
        reproduction_difficulty="low",
        hardware_requirement="single GPU",
        license="MIT",
    )
    bare = BaselineCandidate(project_id="p", name="bare baseline", method_summary="unknowns")

    strong_score = score_baseline(strong, goal="")
    bare_score = score_baseline(bare, goal="")

    assert set(strong_score.axes) == _AXES
    assert strong_score.axes["code_availability"] == 1.0
    assert bare_score.axes["code_availability"] == 0.0
    # weighted, not a flat average: a fully-loaded baseline clears 0.8.
    assert strong_score.overall > 0.8
    assert strong_score.overall > bare_score.overall
    assert 0.0 <= bare_score.overall <= 1.0
    assert strong_score.explanation


def test_score_baseline_rewards_relevance_to_the_goal():
    candidate = BaselineCandidate(
        project_id="p",
        name="retrieval augmented generation",
        method_summary="dense retrieval feeding a generator",
    )
    on_topic = score_baseline(candidate, goal="retrieval augmented generation for QA")
    off_topic = score_baseline(candidate, goal="convolutional image classification")
    assert on_topic.axes["relevance_to_user_goal"] > off_topic.axes["relevance_to_user_goal"]


@pytest.mark.asyncio
async def test_extract_baseline_candidates_is_idempotent(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    paper = Paper(project_id=project.id, title="RAG", code_url="https://github.com/example/rag")
    await repo.create_paper(paper)
    await repo.create_paper_note(
        PaperNote(paper_id=paper.id, method="retriever + generator", datasets=["NQ"], metrics=["EM"])
    )

    first = await extract_baseline_candidates(repo, project.id)
    second = await extract_baseline_candidates(repo, project.id)

    assert len(first) == 1
    assert first[0].paper_id == paper.id
    assert first[0].code_url == "https://github.com/example/rag"
    assert second == []  # the paper is already covered, so nothing is duplicated


@pytest.mark.asyncio
async def test_rank_baselines_orders_by_overall_and_persists_scores(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    await repo.create_baseline(
        BaselineCandidate(
            project_id=project.id,
            name="strong",
            method_summary="m",
            code_url="https://github.com/example/strong",
            dataset="MMLU",
            reproduction_difficulty="low",
            license="Apache-2.0",
        )
    )
    await repo.create_baseline(
        BaselineCandidate(project_id=project.id, name="weak", method_summary="m")
    )

    ranking = await rank_baselines(repo, project.id, goal="")

    assert [s.name for s in ranking] == ["strong", "weak"]
    assert ranking[0].overall >= ranking[1].overall
    # rank_score and selection_reason are written back onto every baseline.
    persisted = await repo.list_project_baselines(project.id)
    assert all(b.rank_score is not None and b.selection_reason for b in persisted)
