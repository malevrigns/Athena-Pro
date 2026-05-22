"""Enumerations for Research OS domain models."""

from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    draft = "draft"
    planning = "planning"
    running = "running"
    waiting_review = "waiting_review"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class PaperScreeningStatus(StrEnum):
    candidate = "candidate"
    included = "included"
    excluded = "excluded"
    read = "read"


class ReviewDecision(StrEnum):
    pending = "pending"
    approved = "approved"
    changes_requested = "changes_requested"
    rejected = "rejected"


class CheckpointType(StrEnum):
    """The four runtime stages that block on human review (roadmap section 11)."""

    plan_review = "plan_review"
    baseline_selection = "baseline_selection"
    experiment_execution = "experiment_execution"
    citation_audit = "citation_audit"


class CheckpointStatus(StrEnum):
    pending = "pending"
    decided = "decided"


class ClaimType(StrEnum):
    """Canonical claim categories (roadmap section 5.4)."""

    method = "method"
    dataset = "dataset"
    metric = "metric"
    result = "result"
    limitation = "limitation"
    comparison = "comparison"
    implementation = "implementation"
    idea = "idea"
