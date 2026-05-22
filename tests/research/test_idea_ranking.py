"""Tests for research idea multi-axis ranking (plan section 7.2)."""

from __future__ import annotations

import pytest

from athena.research.domain import ResearchIdea, ResearchProject
from athena.research.services.ideas import rank_ideas, score_idea

_AXES = {
    "novelty",
    "feasibility",
    "expected_gain",
    "evidence_support",
    "risk",
    "experiment_cost",
    "baseline_compatibility",
}


def _idea(**overrides) -> ResearchIdea:
    base = dict(
        project_id="p",
        title="idea",
        motivation="m",
        core_hypothesis="h",
        method_sketch="s",
    )
    return ResearchIdea(**{**base, **overrides})


def test_score_idea_keeps_every_axis_and_penalizes_risk():
    grounded = _idea(
        expected_advantage="clear gain over the baseline",
        required_baselines=["B1"],
        required_datasets=["D1"],
        novelty_score=0.9,
        feasibility_score=0.8,
        risk_score=0.1,
        evidence_ids=["e1", "e2"],
    )
    risky = grounded.model_copy(update={"risk_score": 0.95})

    grounded_score = score_idea(grounded)
    risky_score = score_idea(risky)

    assert set(grounded_score.axes) == _AXES
    # the only difference is risk, so the risky idea must score lower.
    assert grounded_score.overall > risky_score.overall
    assert grounded_score.explanation


def test_score_idea_uses_neutral_defaults_for_unscored_axes():
    bare = _idea()
    score = score_idea(bare)
    assert score.axes["novelty"] == 0.5  # no novelty_score supplied
    assert score.axes["evidence_support"] == 0.0  # no linked evidence
    assert 0.0 <= score.overall <= 1.0


@pytest.mark.asyncio
async def test_rank_ideas_orders_by_overall_and_persists_scores(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    await repo.create_idea(
        _idea(
            project_id=project.id,
            title="strong",
            expected_advantage="big gain",
            required_baselines=["B1"],
            novelty_score=0.9,
            feasibility_score=0.9,
            risk_score=0.1,
            evidence_ids=["e1", "e2"],
        )
    )
    await repo.create_idea(
        _idea(project_id=project.id, title="weak", novelty_score=0.2, risk_score=0.9)
    )

    ranking = await rank_ideas(repo, project.id)

    assert [s.title for s in ranking] == ["strong", "weak"]
    assert ranking[0].overall >= ranking[1].overall
    # overall_score is written back onto every idea.
    persisted = await repo.list_project_ideas(project.id)
    assert all(idea.overall_score is not None for idea in persisted)
