"""Reusable Research OS service functions."""

from __future__ import annotations

from .claims import ClaimExtractionResult, extract_claims
from .evidence_audit import EvidenceAuditReport, UnsupportedClaim, check_evidence_completeness
from .projects import (
    create_paper,
    create_paper_note,
    create_project,
    get_project_tool_trace,
    get_tool_trace,
)
from .paper_reader import extract_paper_note
from .tool_execution import execute_tool_with_trace

__all__ = [
    "ClaimExtractionResult",
    "EvidenceAuditReport",
    "UnsupportedClaim",
    "check_evidence_completeness",
    "create_paper",
    "create_paper_note",
    "create_project",
    "execute_tool_with_trace",
    "extract_claims",
    "extract_paper_note",
    "get_project_tool_trace",
    "get_tool_trace",
]
