"""Baseline candidate extraction and multi-axis ranking (plan section 7.1).

Ranking is deliberately *not* a single averaged number. Each baseline is scored
on seven named axes; the overall score is an explicit weighted sum and every
per-axis score plus a human-readable explanation is preserved, so a user can
see *why* one baseline outranks another before committing to reproduce it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from athena.research.domain import BaselineCandidate, Paper, PaperNote
from athena.research.persistence import ResearchRepository

# Axis weights — explicit and summing to 1.0 (plan section 7.1: "总分不是简单平均").
_WEIGHTS: dict[str, float] = {
    "reported_strength": 0.18,
    "code_availability": 0.20,
    "dataset_availability": 0.14,
    "implementation_complexity": 0.16,
    "hardware_cost": 0.12,
    "license_safety": 0.08,
    "relevance_to_user_goal": 0.12,
}
_REPORTED_SCORE_MAX = 240
_STOPWORDS = frozenset(
    {"a", "an", "the", "of", "for", "and", "or", "to", "in", "on", "with", "via", "using"}
)


class BaselineScore(BaseModel):
    """A baseline's per-axis scores, weighted overall, and an explanation."""

    baseline_id: str
    name: str
    axes: dict[str, float]
    overall: float
    explanation: str


async def extract_baseline_candidates(
    repository: ResearchRepository,
    project_id: str,
) -> list[BaselineCandidate]:
    """Derive baseline candidates from papers that have a method reading note.

    Papers that already have a baseline candidate are skipped, so the call is
    safe to repeat.
    """
    project = await repository.get_project(project_id)
    if project is None:
        raise LookupError("project not found")

    existing = await repository.list_project_baselines(project_id)
    covered = {b.paper_id for b in existing if b.paper_id}
    papers = await repository.list_project_papers(project_id, limit=500)

    created: list[BaselineCandidate] = []
    for paper in papers:
        if paper.id in covered:
            continue
        notes = await repository.list_paper_notes(paper.id)
        note = notes[0] if notes else None
        if note is None or not note.method:
            continue
        candidate = _candidate_from_paper(project_id, paper, note)
        await repository.create_baseline(candidate)
        created.append(candidate)
    return created


async def rank_baselines(
    repository: ResearchRepository,
    project_id: str,
    *,
    goal: str = "",
) -> list[BaselineScore]:
    """Score and rank a project's baselines; persist rank_score back on each."""

    baselines = await repository.list_project_baselines(project_id)
    scored = sorted(
        (score_baseline(baseline, goal=goal) for baseline in baselines),
        key=lambda s: s.overall,
        reverse=True,
    )
    by_id = {b.id: b for b in baselines}
    for score in scored:
        baseline = by_id[score.baseline_id]
        await repository.upsert_baseline(
            baseline.model_copy(
                update={"rank_score": score.overall, "selection_reason": score.explanation}
            )
        )
    return scored


def score_baseline(baseline: BaselineCandidate, *, goal: str = "") -> BaselineScore:
    """Score one baseline on every axis and combine into a weighted overall."""

    axes = {
        "reported_strength": 0.7 if baseline.reported_score else 0.3,
        "code_availability": 1.0 if baseline.code_url else 0.0,
        "dataset_availability": 1.0 if baseline.dataset else 0.0,
        "implementation_complexity": _complexity_score(baseline.reproduction_difficulty),
        "hardware_cost": _hardware_score(baseline.hardware_requirement),
        "license_safety": _license_score(baseline.license),
        "relevance_to_user_goal": _relevance_score(baseline, goal),
    }
    overall = round(sum(axes[name] * weight for name, weight in _WEIGHTS.items()), 4)
    return BaselineScore(
        baseline_id=baseline.id,
        name=baseline.name,
        axes={name: round(value, 4) for name, value in axes.items()},
        overall=overall,
        explanation=_explain(axes),
    )


def _candidate_from_paper(project_id: str, paper: Paper, note: PaperNote) -> BaselineCandidate:
    datasets = note.datasets or paper.dataset_mentions
    return BaselineCandidate(
        project_id=project_id,
        name=paper.title,
        method_summary=note.method or paper.title,
        paper_id=paper.id,
        code_url=paper.code_url,
        dataset=datasets[0] if datasets else None,
        metric=note.metrics[0] if note.metrics else None,
        reported_score=_truncate(note.main_results),
    )


def _complexity_score(difficulty: str | None) -> float:
    text = (difficulty or "").strip().lower()
    if not text:
        return 0.5
    if any(word in text for word in ("low", "easy", "trivial")):
        return 1.0
    if "medium" in text or "moderate" in text:
        return 0.6
    if any(word in text for word in ("high", "hard", "difficult")):
        return 0.3
    return 0.5


def _hardware_score(requirement: str | None) -> float:
    text = (requirement or "").strip().lower()
    if not text:
        return 0.6
    if "cpu" in text:
        return 1.0
    if any(word in text for word in ("cluster", "multi", "8x", "8 gpu", "tpu")):
        return 0.3
    if "gpu" in text:
        return 0.8
    return 0.6


def _license_score(license_text: str | None) -> float:
    text = (license_text or "").strip().lower()
    if not text:
        return 0.5
    if any(word in text for word in ("non-commercial", "noncommercial", "cc-by-nc", "research only")):
        return 0.3
    if any(word in text for word in ("mit", "apache", "bsd")):
        return 1.0
    if "gpl" in text:
        return 0.6
    return 0.5


def _relevance_score(baseline: BaselineCandidate, goal: str) -> float:
    goal_tokens = _tokens(goal)
    if not goal_tokens:
        return 0.5
    text_tokens = _tokens(f"{baseline.name} {baseline.method_summary}")
    if not text_tokens:
        return 0.0
    overlap = len(goal_tokens & text_tokens) / len(goal_tokens)
    return round(min(1.0, overlap), 4)


def _tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    word: list[str] = []
    for char in text.lower():
        if char.isalnum():
            word.append(char)
        elif word:
            tokens.add("".join(word))
            word = []
    if word:
        tokens.add("".join(word))
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS}


def _explain(axes: dict[str, float]) -> str:
    best = max(axes, key=lambda name: axes[name])
    worst = min(axes, key=lambda name: axes[name])
    return (
        f"strongest on {best} ({axes[best]:.2f}), weakest on {worst} ({axes[worst]:.2f})"
    )


def _truncate(text: str | None) -> str | None:
    if not text:
        return None
    collapsed = " ".join(text.split())
    if len(collapsed) <= _REPORTED_SCORE_MAX:
        return collapsed
    return collapsed[: _REPORTED_SCORE_MAX - 1].rstrip() + "…"
