"""Tests for the method taxonomy builder (roadmap section 5.6)."""

from __future__ import annotations

import pytest

from athena.research.domain import Paper, PaperNote, ResearchProject
from athena.research.services.taxonomy import build_taxonomy


@pytest.mark.asyncio
async def test_build_taxonomy_links_methods_to_shared_datasets(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    paper_a = Paper(project_id=project.id, title="Method A", year=2021)
    paper_b = Paper(project_id=project.id, title="Method B", year=2023)
    await repo.create_paper(paper_a)
    await repo.create_paper(paper_b)
    await repo.create_paper_note(
        PaperNote(
            paper_id=paper_a.id,
            method="retriever A",
            datasets=["MMLU"],
            metrics=["accuracy"],
            limitations="latency grows with retrieval depth",
        )
    )
    await repo.create_paper_note(
        PaperNote(paper_id=paper_b.id, method="retriever B", datasets=["MMLU"], metrics=["f1"])
    )

    taxonomy = await build_taxonomy(repo, project.id)

    methods = [n for n in taxonomy.nodes if n["type"] == "method_family"]
    datasets = [n for n in taxonomy.nodes if n["type"] == "dataset"]
    protocols = [n for n in taxonomy.nodes if n["type"] == "evaluation_protocol"]
    assert len(methods) == 2
    assert len(datasets) == 1  # MMLU is shared, so it is one node
    assert len(protocols) == 2  # accuracy, f1
    # both methods point at the shared dataset node
    dataset_id = datasets[0]["id"]
    evaluated_on = [e for e in taxonomy.edges if e["type"] == "evaluated_on"]
    assert {e["target"] for e in evaluated_on} == {dataset_id}
    assert len(evaluated_on) == 2
    assert "latency" in " ".join(taxonomy.open_problems)
    # the taxonomy was persisted and is retrievable as the project's latest.
    latest = await repo.latest_project_taxonomy(project.id)
    assert latest is not None and latest.id == taxonomy.id


@pytest.mark.asyncio
async def test_build_taxonomy_rejects_unknown_project(make_store):
    repo = await make_store().research_repository()
    with pytest.raises(LookupError):
        await build_taxonomy(repo, "proj_missing")
