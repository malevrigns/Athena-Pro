"""Benchmark candidate extraction (roadmap section 12.3 / 12.4).

A benchmark is a dataset the project's papers evaluate on. This derives one
`Benchmark` per distinct dataset across the paper library: `adoption_count` —
how many papers use it — is the ranking signal for how standard and comparable
the benchmark is. `list_project_benchmarks` already returns them adoption-first,
so this module only needs the extraction step.

Note: metrics are aggregated coarsely — every metric named in a paper's note is
attached to each dataset that paper mentions, since notes do not bind a metric
to a specific dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from athena.research.domain import Benchmark
from athena.research.persistence import ResearchRepository


@dataclass
class _DatasetTally:
    label: str
    paper_ids: set[str] = field(default_factory=set)
    metrics: set[str] = field(default_factory=set)


async def extract_benchmark_candidates(
    repository: ResearchRepository,
    project_id: str,
) -> list[Benchmark]:
    """Derive benchmark candidates from the datasets the project's papers use.

    Datasets that already have a `Benchmark` are skipped, so the call is safe
    to repeat.
    """
    project = await repository.get_project(project_id)
    if project is None:
        raise LookupError("project not found")

    tallies: dict[str, _DatasetTally] = {}
    for paper in await repository.list_project_papers(project_id, limit=500):
        notes = await repository.list_paper_notes(paper.id)
        note = notes[0] if notes else None
        datasets = (note.datasets if note and note.datasets else paper.dataset_mentions) or []
        metrics = [m.strip() for m in (note.metrics if note else []) if m.strip()]
        for dataset in datasets:
            label = dataset.strip()
            if not label:
                continue
            tally = tallies.setdefault(label.lower(), _DatasetTally(label=label))
            tally.paper_ids.add(paper.id)
            tally.metrics.update(metrics)

    existing = await repository.list_project_benchmarks(project_id)
    covered = {b.dataset.strip().lower() for b in existing}

    created: list[Benchmark] = []
    for key, tally in tallies.items():
        if key in covered:
            continue
        benchmark = Benchmark(
            project_id=project_id,
            name=tally.label,
            dataset=tally.label,
            metrics=sorted(tally.metrics),
            source_paper_ids=sorted(tally.paper_ids),
            adoption_count=len(tally.paper_ids),
        )
        await repository.create_benchmark(benchmark)
        created.append(benchmark)
    return created
