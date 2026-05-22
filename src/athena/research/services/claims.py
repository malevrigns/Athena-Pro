"""Claim and evidence extraction service (roadmap section 6.3).

For an included paper this derives a small set of verifiable claims — method,
dataset, result, limitation and (when code exists) implementation — and grounds
each one in an `Evidence` record. Extraction is deterministic: every evidence
`quote` is text taken verbatim from a persisted asset (the paper's reading note
or its metadata), so a claim is never created without traceable support.

When a structured `PaperNote` exists it is the evidence source; otherwise the
service falls back to the paper's abstract and metadata and marks the evidence
`unverified` so the gap is visible to the evidence completeness check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from athena.research.domain import Claim, ClaimType, Evidence, Paper, PaperNote, ResearchProject
from athena.research.persistence import ResearchRepository

_QUOTE_MAX = 600
_CLAIM_TEXT_MAX = 400

ExtractionSource = Literal["paper_note", "paper_metadata"]


@dataclass(frozen=True)
class ClaimExtractionResult:
    project_id: str
    paper_id: str
    extraction_source: ExtractionSource
    claims: list[Claim] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "project_id": self.project_id,
            "paper_id": self.paper_id,
            "extraction_source": self.extraction_source,
            "claim_count": len(self.claims),
            "evidence_count": len(self.evidence),
            "claims": [claim.model_dump(mode="json") for claim in self.claims],
            "evidence": [item.model_dump(mode="json") for item in self.evidence],
        }


@dataclass(frozen=True)
class _ClaimDraft:
    claim_type: ClaimType
    section: str
    text: str
    quote: str
    source_url: str | None


async def extract_claims(
    repository: ResearchRepository,
    *,
    project_id: str,
    paper_id: str,
) -> ClaimExtractionResult:
    """Extract and persist grounded claims for one project paper."""

    project, paper = await _load_project_paper(repository, project_id, paper_id)
    notes = await repository.list_paper_notes(paper_id)
    note = notes[0] if notes else None

    drafts = _drafts_from_note(paper, note) if note else _drafts_from_metadata(paper)
    source: ExtractionSource = "paper_note" if note else "paper_metadata"
    verification = "verified" if note else "unverified"
    confidence = 0.6 if note else 0.4

    claims: list[Claim] = []
    evidence: list[Evidence] = []
    for draft in drafts:
        quote = _quote(draft.quote)
        evidence_record = Evidence(
            claim_id="",  # set below once the claim id exists
            source_type=source,
            source_url=draft.source_url or paper.url,
            paper_id=paper.id,
            section=draft.section,
            quote=quote,
            normalized_text=" ".join(quote.split()),
            confidence=confidence,
            verification_status=verification,
        )
        claim = Claim(
            project_id=project.id,
            paper_id=paper.id,
            text=draft.text,
            claim_type=draft.claim_type.value,
            section=draft.section,
            confidence=confidence,
            evidence_ids=[evidence_record.id],
        )
        evidence_record = evidence_record.model_copy(update={"claim_id": claim.id})
        await repository.create_claim(claim)
        await repository.create_evidence(evidence_record)
        claims.append(claim)
        evidence.append(evidence_record)

    return ClaimExtractionResult(
        project_id=project.id,
        paper_id=paper.id,
        extraction_source=source,
        claims=claims,
        evidence=evidence,
    )


async def _load_project_paper(
    repository: ResearchRepository,
    project_id: str,
    paper_id: str,
) -> tuple[ResearchProject, Paper]:
    project = await repository.get_project(project_id)
    if project is None:
        raise LookupError("project not found")
    paper = await repository.get_paper(paper_id)
    if paper is None or paper.project_id != project_id:
        raise LookupError("paper not found")
    return project, paper


def _drafts_from_note(paper: Paper, note: PaperNote) -> list[_ClaimDraft]:
    drafts: list[_ClaimDraft] = []
    if note.method:
        drafts.append(
            _ClaimDraft(ClaimType.method, "method", _claim_text(note.method), note.method, paper.url)
        )
    datasets = note.datasets or paper.dataset_mentions
    if datasets:
        joined = ", ".join(datasets)
        drafts.append(
            _ClaimDraft(
                ClaimType.dataset,
                "datasets",
                _claim_text(f"Evaluated on {joined}."),
                joined,
                paper.url,
            )
        )
    if note.main_results:
        drafts.append(
            _ClaimDraft(
                ClaimType.result,
                "results",
                _claim_text(note.main_results),
                note.main_results,
                paper.url,
            )
        )
    if note.limitations:
        drafts.append(
            _ClaimDraft(
                ClaimType.limitation,
                "limitations",
                _claim_text(note.limitations),
                note.limitations,
                paper.url,
            )
        )
    if paper.code_url:
        drafts.append(_implementation_draft(paper))
    return drafts


def _drafts_from_metadata(paper: Paper) -> list[_ClaimDraft]:
    drafts: list[_ClaimDraft] = []
    if paper.abstract:
        drafts.append(
            _ClaimDraft(
                ClaimType.method,
                "abstract",
                _claim_text(paper.abstract),
                paper.abstract,
                paper.url,
            )
        )
    if paper.dataset_mentions:
        joined = ", ".join(paper.dataset_mentions)
        drafts.append(
            _ClaimDraft(
                ClaimType.dataset,
                "metadata",
                _claim_text(f"Mentions datasets: {joined}."),
                joined,
                paper.url,
            )
        )
    if paper.code_url:
        drafts.append(_implementation_draft(paper))
    return drafts


def _implementation_draft(paper: Paper) -> _ClaimDraft:
    return _ClaimDraft(
        ClaimType.implementation,
        "code",
        f"An implementation is available at {paper.code_url}.",
        f"code_url: {paper.code_url}",
        paper.code_url,
    )


def _claim_text(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= _CLAIM_TEXT_MAX:
        return collapsed
    return collapsed[: _CLAIM_TEXT_MAX - 1].rstrip() + "…"


def _quote(text: str) -> str:
    return text if len(text) <= _QUOTE_MAX else text[:_QUOTE_MAX]
