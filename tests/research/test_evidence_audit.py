"""Tests for the evidence completeness check (roadmap section 15)."""

from __future__ import annotations

import pytest

from athena.research.domain import Claim, ClaimType, Evidence, ResearchProject
from athena.research.services.evidence_audit import check_evidence_completeness


@pytest.mark.asyncio
async def test_audit_separates_supported_and_unsupported_claims(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)

    supported = Claim(project_id=project.id, text="grounded claim", claim_type=ClaimType.result)
    await repo.create_claim(supported)
    await repo.create_evidence(
        Evidence(
            claim_id=supported.id,
            source_type="paper_note",
            quote="we observe a 3 point gain",
            verification_status="verified",
        )
    )
    unsupported = Claim(
        project_id=project.id,
        text="claim with no evidence",
        claim_type=ClaimType.method,
        paper_id="paper_x",
    )
    await repo.create_claim(unsupported)

    report = await check_evidence_completeness(repo, project.id)

    assert report.total_claims == 2
    assert report.supported_claims == 1
    assert report.verified_claims == 1
    assert report.unsupported_claims == 1
    assert report.completeness_ratio == 0.5
    assert [c.claim_id for c in report.unsupported] == [unsupported.id]
    assert report.unsupported[0].paper_id == "paper_x"


@pytest.mark.asyncio
async def test_audit_counts_supported_but_unverified_claims(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    claim = Claim(project_id=project.id, text="metadata claim", claim_type=ClaimType.method)
    await repo.create_claim(claim)
    await repo.create_evidence(
        Evidence(claim_id=claim.id, source_type="paper", verification_status="unverified")
    )

    report = await check_evidence_completeness(repo, project.id)

    assert report.supported_claims == 1
    assert report.verified_claims == 0
    assert report.completeness_ratio == 1.0


@pytest.mark.asyncio
async def test_audit_of_empty_project_is_complete(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="empty", research_question="Q?")
    await repo.create_project(project)

    report = await check_evidence_completeness(repo, project.id)

    assert report.total_claims == 0
    assert report.completeness_ratio == 1.0
    assert report.unsupported == []
