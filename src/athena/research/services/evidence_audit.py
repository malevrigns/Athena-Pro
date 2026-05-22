"""Evidence completeness check (roadmap section 15 / plan section 6.4).

A research conclusion is only trustworthy when it can be traced to evidence.
This service audits every claim in a project and reports which claims lack a
linked `Evidence` record, so unsupported claims surface before — not after —
they reach a final report.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from athena.research.persistence import ResearchRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UnsupportedClaim(BaseModel):
    claim_id: str
    claim_type: str
    text: str
    paper_id: str | None = None


class EvidenceAuditReport(BaseModel):
    project_id: str
    total_claims: int
    supported_claims: int
    unsupported_claims: int
    verified_claims: int
    completeness_ratio: float
    unsupported: list[UnsupportedClaim] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=_utcnow)


async def check_evidence_completeness(
    repository: ResearchRepository,
    project_id: str,
) -> EvidenceAuditReport:
    """Audit a project's claims for linked, verified evidence."""

    claims = await repository.list_project_claims(project_id)
    supported = 0
    verified = 0
    unsupported: list[UnsupportedClaim] = []

    for claim in claims:
        evidence = await repository.list_claim_evidence(claim.id)
        if evidence:
            supported += 1
            if any(item.verification_status == "verified" for item in evidence):
                verified += 1
        else:
            unsupported.append(
                UnsupportedClaim(
                    claim_id=claim.id,
                    claim_type=claim.claim_type,
                    text=claim.text,
                    paper_id=claim.paper_id,
                )
            )

    total = len(claims)
    return EvidenceAuditReport(
        project_id=project_id,
        total_claims=total,
        supported_claims=supported,
        unsupported_claims=len(unsupported),
        verified_claims=verified,
        completeness_ratio=round(supported / total, 4) if total else 1.0,
        unsupported=unsupported,
    )
