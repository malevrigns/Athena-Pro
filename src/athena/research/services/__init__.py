"""Reusable Research OS service functions."""

from __future__ import annotations

from .baselines import BaselineScore, extract_baseline_candidates, rank_baselines, score_baseline
from .benchmarks import extract_benchmark_candidates
from .claims import ClaimExtractionResult, extract_claims
from .evidence_audit import EvidenceAuditReport, UnsupportedClaim, check_evidence_completeness
from .ideas import IdeaScore, rank_ideas, score_idea
from .projects import (
    create_paper,
    create_paper_note,
    create_project,
    get_project_tool_trace,
    get_tool_trace,
)
from .paper_reader import extract_paper_note
from .selection import select_baseline, select_benchmark
from .taxonomy import build_taxonomy
from .tool_execution import execute_tool_with_trace

__all__ = [
    "BaselineScore",
    "ClaimExtractionResult",
    "EvidenceAuditReport",
    "IdeaScore",
    "UnsupportedClaim",
    "build_taxonomy",
    "check_evidence_completeness",
    "create_paper",
    "create_paper_note",
    "create_project",
    "execute_tool_with_trace",
    "extract_baseline_candidates",
    "extract_benchmark_candidates",
    "extract_claims",
    "extract_paper_note",
    "get_project_tool_trace",
    "get_tool_trace",
    "rank_baselines",
    "rank_ideas",
    "score_baseline",
    "score_idea",
    "select_baseline",
    "select_benchmark",
]
