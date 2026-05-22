"""Method taxonomy builder (roadmap section 5.6 / 9.3).

Builds a `MethodTaxonomy` from a project's papers and their reading notes:
each paper becomes a method-family node linked to the datasets it is evaluated
on and the metrics it is measured by. The build is deterministic — it derives
the graph from persisted assets only — so the same library always produces the
same taxonomy and the result is testable without an LLM.
"""

from __future__ import annotations

from athena.research.domain import MethodTaxonomy, Paper, PaperNote
from athena.research.persistence import ResearchRepository

_OPEN_PROBLEM_MAX = 240


async def build_taxonomy(repository: ResearchRepository, project_id: str) -> MethodTaxonomy:
    """Build and persist a method taxonomy for a project."""

    project = await repository.get_project(project_id)
    if project is None:
        raise LookupError("project not found")

    papers = await repository.list_project_papers(project_id, limit=500)
    nodes: list[dict] = []
    edges: list[dict] = []
    dataset_nodes: dict[str, str] = {}
    metric_nodes: dict[str, str] = {}
    open_problems: list[str] = []
    method_count = 0

    for paper in papers:
        notes = await repository.list_paper_notes(paper.id)
        note = notes[0] if notes else None
        method_id = f"method:{paper.id}"
        method_count += 1
        nodes.append(
            {
                "id": method_id,
                "type": "method_family",
                "label": paper.title,
                "year": paper.year,
                "paper_id": paper.id,
            }
        )
        for dataset in _datasets(paper, note):
            node_id = _ensure_node(dataset_nodes, nodes, prefix="dataset", type_="dataset", label=dataset)
            edges.append({"source": method_id, "target": node_id, "type": "evaluated_on"})
        if note:
            for metric in note.metrics:
                node_id = _ensure_node(
                    metric_nodes, nodes, prefix="metric", type_="evaluation_protocol", label=metric
                )
                edges.append({"source": method_id, "target": node_id, "type": "measured_by"})
            if note.limitations:
                open_problems.append(_truncate(note.limitations))

    summary = (
        f"{method_count} method families across {len(dataset_nodes)} datasets and "
        f"{len(metric_nodes)} evaluation protocols ({len(papers)} papers)."
    )
    taxonomy = MethodTaxonomy(
        project_id=project_id,
        nodes=nodes,
        edges=edges,
        summary=summary,
        open_problems=_dedupe(open_problems),
    )
    await repository.create_taxonomy(taxonomy)
    return taxonomy


def _datasets(paper: Paper, note: PaperNote | None) -> list[str]:
    if note and note.datasets:
        return note.datasets
    return paper.dataset_mentions


def _ensure_node(
    index: dict[str, str],
    nodes: list[dict],
    *,
    prefix: str,
    type_: str,
    label: str,
) -> str:
    key = " ".join(label.strip().lower().split())
    node_id = index.get(key)
    if node_id is None:
        node_id = f"{prefix}:{key}"
        index[key] = node_id
        nodes.append({"id": node_id, "type": type_, "label": label})
    return node_id


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(value)
    return unique


def _truncate(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= _OPEN_PROBLEM_MAX:
        return collapsed
    return collapsed[: _OPEN_PROBLEM_MAX - 1].rstrip() + "…"
