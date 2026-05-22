"""Research OS typed event protocol (Phase 1, step 3).

Additive to the legacy `athena.schemas` event protocol — see `schemas.py`.
"""

from __future__ import annotations

from .schemas import (
    RESEARCH_EVENT_ADAPTER,
    RESEARCH_EVENT_TYPES,
    ArtifactCreatedEvent,
    ArtifactCreatedPayload,
    ClaimExtractedEvent,
    ClaimExtractedPayload,
    DoneEvent,
    DonePayload,
    ErrorEvent,
    ErrorPayload,
    PaperFoundEvent,
    PaperFoundPayload,
    PlanReviewRequiredEvent,
    PlanReviewRequiredPayload,
    ResearchEvent,
    ResearchEventBase,
    StatusEvent,
    StatusPayload,
    ToolCallEvent,
    ToolCallPayload,
    ToolObservationEvent,
    ToolObservationPayload,
)

__all__ = [
    "RESEARCH_EVENT_ADAPTER",
    "RESEARCH_EVENT_TYPES",
    "ResearchEvent",
    "ResearchEventBase",
    "ArtifactCreatedEvent",
    "ArtifactCreatedPayload",
    "ClaimExtractedEvent",
    "ClaimExtractedPayload",
    "DoneEvent",
    "DonePayload",
    "ErrorEvent",
    "ErrorPayload",
    "PaperFoundEvent",
    "PaperFoundPayload",
    "PlanReviewRequiredEvent",
    "PlanReviewRequiredPayload",
    "StatusEvent",
    "StatusPayload",
    "ToolCallEvent",
    "ToolCallPayload",
    "ToolObservationEvent",
    "ToolObservationPayload",
]
