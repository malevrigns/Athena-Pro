"""Research idea multi-axis ranking (plan section 7.2).

An idea's `novelty`, `feasibility` and `risk` are subjective inputs supplied
when the idea is created (by a human or an idea-generation agent). This service
combines them with structural signals it *can* measure deterministically —
evidence support, experiment cost, baseline compatibility — into one explicit
weighted overall score, and persists it back onto the idea.
"""

from __future__ import annotations

from pydantic import BaseModel

from athena.research.domain import ResearchIdea
from athena.research.persistence import ResearchRepository

# Axis weights — explicit and summing to 1.0. `risk` contributes inverted
# (1 - risk): a higher risk lowers the overall score.
_WEIGHTS: dict[str, float] = {
    "novelty": 0.22,
    "feasibility": 0.18,
    "expected_gain": 0.18,
    "evidence_support": 0.14,
    "risk": 0.12,
    "experiment_cost": 0.08,
    "baseline_compatibility": 0.08,
}
_POSITIVE_AXES = tuple(name for name in _WEIGHTS if name != "risk")


class IdeaScore(BaseModel):
    """An idea's per-axis scores, weighted overall, and an explanation."""

    idea_id: str
    title: str
    axes: dict[str, float]
    overall: float
    explanation: str


async def rank_ideas(repository: ResearchRepository, project_id: str) -> list[IdeaScore]:
    """Score and rank a project's ideas; persist overall_score back on each."""

    ideas = await repository.list_project_ideas(project_id)
    scored = sorted(
        (score_idea(idea) for idea in ideas),
        key=lambda s: s.overall,
        reverse=True,
    )
    by_id = {idea.id: idea for idea in ideas}
    for score in scored:
        idea = by_id[score.idea_id]
        await repository.upsert_idea(idea.model_copy(update={"overall_score": score.overall}))
    return scored


def score_idea(idea: ResearchIdea) -> IdeaScore:
    """Score one idea on every axis and combine into a weighted overall."""

    axes = {
        "novelty": _default(idea.novelty_score, 0.5),
        "feasibility": _default(idea.feasibility_score, 0.5),
        "expected_gain": _expected_gain(idea),
        "evidence_support": min(1.0, len(idea.evidence_ids) * 0.25),
        "risk": _default(idea.risk_score, 0.5),
        "experiment_cost": _experiment_cost(idea),
        "baseline_compatibility": 1.0 if idea.required_baselines else 0.4,
    }
    overall = round(
        sum(
            (1.0 - axes[name] if name == "risk" else axes[name]) * weight
            for name, weight in _WEIGHTS.items()
        ),
        4,
    )
    return IdeaScore(
        idea_id=idea.id,
        title=idea.title,
        axes={name: round(value, 4) for name, value in axes.items()},
        overall=overall,
        explanation=_explain(axes),
    )


def _default(value: float | None, fallback: float) -> float:
    return fallback if value is None else max(0.0, min(1.0, value))


def _expected_gain(idea: ResearchIdea) -> float:
    if idea.expected_advantage:
        return 0.75
    if idea.method_sketch:
        return 0.45
    return 0.3


def _experiment_cost(idea: ResearchIdea) -> float:
    """Fewer required baselines/datasets means a cheaper experiment, scored higher."""
    demand = len(idea.required_baselines) + len(idea.required_datasets)
    return round(max(0.2, 1.0 - 0.12 * demand), 4)


def _explain(axes: dict[str, float]) -> str:
    best = max(_POSITIVE_AXES, key=lambda name: axes[name])
    worst = min(_POSITIVE_AXES, key=lambda name: axes[name])
    return (
        f"strongest on {best} ({axes[best]:.2f}), weakest on {worst} ({axes[worst]:.2f}); "
        f"risk {axes['risk']:.2f}"
    )
