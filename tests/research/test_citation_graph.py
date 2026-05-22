"""Tests for the citation_graph tool (roadmap section 6.1)."""

from __future__ import annotations

import pytest

from athena.research.domain import Paper, ResearchProject
from athena.research.tools.citation_graph import build_citation_graph_tool


async def _seed(repo):
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    # rag_2020 and rag_2023 share a dataset and title vocabulary -> related.
    rag_2020 = Paper(
        project_id=project.id,
        title="Retrieval Augmented Generation for knowledge tasks",
        authors=["Alice"],
        year=2020,
        dataset_mentions=["Natural Questions"],
        citation_count=900,
    )
    rag_2023 = Paper(
        project_id=project.id,
        title="Improved Retrieval Augmented Generation reranking",
        authors=["Bob"],
        year=2023,
        dataset_mentions=["Natural Questions"],
        citation_count=40,
    )
    unrelated = Paper(
        project_id=project.id,
        title="A study of convolutional image classifiers",
        authors=["Carol"],
        year=2019,
    )
    for paper in (rag_2020, rag_2023, unrelated):
        await repo.create_paper(paper)
    return project, rag_2020, rag_2023, unrelated


@pytest.mark.asyncio
async def test_citation_graph_builds_relatedness_edges(make_store):
    repo = await make_store().research_repository()
    project, rag_2020, rag_2023, unrelated = await _seed(repo)

    tool = build_citation_graph_tool(repo)
    result = await tool.handler({"project_id": project.id})

    assert result.ok is True
    payload = result.structured_output
    assert payload["node_count"] == 3
    # the two RAG papers are linked; the image-classification paper is isolated.
    assert payload["edge_count"] == 1
    edge = payload["edges"][0]
    assert {edge["source"], edge["target"]} == {rag_2020.id, rag_2023.id}
    assert edge["shared_datasets"] == 1
    assert unrelated.id not in {edge["source"], edge["target"]}


@pytest.mark.asyncio
async def test_citation_graph_splits_references_and_citations_by_year(make_store):
    repo = await make_store().research_repository()
    project, rag_2020, rag_2023, _ = await _seed(repo)

    tool = build_citation_graph_tool(repo)
    result = await tool.handler({"project_id": project.id, "paper_id": rag_2020.id})

    payload = result.structured_output
    assert payload["paper_id"] == rag_2020.id
    # rag_2023 is newer -> a citation of the 2020 paper.
    assert [n["paper_id"] for n in payload["citations"]] == [rag_2023.id]
    assert payload["references"] == []
    assert [n["paper_id"] for n in payload["influential_citations"]] == [rag_2023.id]


@pytest.mark.asyncio
async def test_citation_graph_rejects_unknown_project_and_paper(make_store):
    repo = await make_store().research_repository()
    project, *_ = await _seed(repo)
    tool = build_citation_graph_tool(repo)

    missing_project = await tool.handler({"project_id": "proj_missing"})
    assert missing_project.ok is False
    assert missing_project.error == "project_not_found"

    missing_paper = await tool.handler({"project_id": project.id, "paper_id": "paper_missing"})
    assert missing_paper.ok is False
    assert missing_paper.error == "paper_not_found"
