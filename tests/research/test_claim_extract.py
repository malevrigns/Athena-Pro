"""Tests for claim/evidence extraction (roadmap section 6.3)."""

from __future__ import annotations

import pytest

from athena.research.domain import ClaimType, Paper, PaperNote, ResearchProject
from athena.research.services.claims import extract_claims
from athena.research.tools.evidence_tools import build_claim_extract_tool


@pytest.mark.asyncio
async def test_extract_claims_from_paper_note_grounds_every_claim(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    paper = Paper(
        project_id=project.id,
        title="Retrieval-Augmented Generation",
        code_url="https://github.com/example/rag",
    )
    await repo.create_paper(paper)
    await repo.create_paper_note(
        PaperNote(
            paper_id=paper.id,
            method="A retriever feeds passages into a generator.",
            datasets=["Natural Questions", "TriviaQA"],
            main_results="Exact match improves by 3 points over the closed-book baseline.",
            limitations="Latency grows with retrieval depth.",
            reproducibility_notes="Configs released.",
        )
    )

    result = await extract_claims(repo, project_id=project.id, paper_id=paper.id)

    assert result.extraction_source == "paper_note"
    kinds = {claim.claim_type for claim in result.claims}
    assert kinds == {
        ClaimType.method,
        ClaimType.dataset,
        ClaimType.result,
        ClaimType.limitation,
        ClaimType.implementation,
    }
    # every claim is persisted and linked to exactly one persisted evidence record.
    assert len(result.evidence) == len(result.claims)
    for claim in result.claims:
        stored = await repo.get_claim(claim.id)
        assert stored is not None
        evidence = await repo.list_claim_evidence(claim.id)
        assert [e.id for e in evidence] == claim.evidence_ids
        assert evidence[0].verification_status == "verified"
        assert evidence[0].quote


@pytest.mark.asyncio
async def test_extract_claims_falls_back_to_metadata_without_a_note(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    paper = Paper(
        project_id=project.id,
        title="Dense Passage Retrieval",
        abstract="We learn dense embeddings for open-domain question answering.",
        dataset_mentions=["Natural Questions"],
    )
    await repo.create_paper(paper)

    result = await extract_claims(repo, project_id=project.id, paper_id=paper.id)

    assert result.extraction_source == "paper_metadata"
    assert {c.claim_type for c in result.claims} == {ClaimType.method, ClaimType.dataset}
    # metadata-only evidence is flagged unverified so the audit can see the gap.
    assert all(e.verification_status == "unverified" for e in result.evidence)
    assert await repo.list_project_claims(project.id) == result.claims


@pytest.mark.asyncio
async def test_claim_extract_tool_reports_not_found(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    tool = build_claim_extract_tool(repo)

    result = await tool.handler({"project_id": project.id, "paper_id": "paper_missing"})

    assert result.ok is False
    assert result.error == "not_found"


@pytest.mark.asyncio
async def test_claim_extract_tool_returns_structured_payload(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    paper = Paper(project_id=project.id, title="A paper", abstract="An abstract.")
    await repo.create_paper(paper)
    tool = build_claim_extract_tool(repo)

    result = await tool.handler({"project_id": project.id, "paper_id": paper.id})

    assert result.ok is True
    payload = result.structured_output
    assert payload["claim_count"] == payload["evidence_count"] == len(payload["claims"])
    assert payload["claims"][0]["evidence_ids"]
