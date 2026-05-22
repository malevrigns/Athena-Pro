"""Baseline and benchmark selection (roadmap section 11.2).

Selecting a baseline or benchmark is a deliberate human decision — the docs are
explicit that it must not be automated (roadmap section 11.2 / 18). These
services only persist a decision a human has already made (via an API call);
they are intentionally not exposed as agent-loop tools.
"""

from __future__ import annotations

from athena.research.domain import BaselineCandidate, Benchmark, SelectionStatus
from athena.research.persistence import ResearchRepository


async def select_baseline(
    repository: ResearchRepository,
    *,
    project_id: str,
    baseline_id: str,
    reason: str | None = None,
) -> BaselineCandidate:
    """Mark a baseline candidate as selected for the project."""
    baseline = await repository.get_baseline(baseline_id)
    if baseline is None or baseline.project_id != project_id:
        raise LookupError("baseline not found")
    selected = baseline.model_copy(
        update={
            "status": SelectionStatus.selected.value,
            "selection_reason": reason if reason is not None else baseline.selection_reason,
        }
    )
    await repository.upsert_baseline(selected)
    return selected


async def select_benchmark(
    repository: ResearchRepository,
    *,
    project_id: str,
    benchmark_id: str,
    reason: str | None = None,
) -> Benchmark:
    """Mark a benchmark as selected for the project."""
    benchmark = await repository.get_benchmark(benchmark_id)
    if benchmark is None or benchmark.project_id != project_id:
        raise LookupError("benchmark not found")
    selected = benchmark.model_copy(
        update={"status": SelectionStatus.selected, "selection_reason": reason}
    )
    await repository.upsert_benchmark(selected)
    return selected
