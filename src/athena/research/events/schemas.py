"""Typed event protocol for Research OS (Phase 1, step 3).

Every Research OS event is one variant of `ResearchEvent`, a Pydantic
discriminated union keyed on `type`. Each variant carries a typed payload
model, so invalid payloads fail validation instead of drifting silently.

This module is additive: it does NOT replace the legacy
`athena.schemas.StreamEvent` / `AthenaEvent` protocol. It is the parallel,
authoritative protocol for the new Research OS layer, consumed by later
phases (frontend Zod mirror, contract tests, ToolRouter trace, asset updates).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

from athena.research.domain import Claim, Paper


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- common envelope -----------------------------------------------------


class ResearchEventBase(BaseModel):
    """Shared envelope carried by every Research OS event variant."""

    task_id: str
    project_id: str | None = None
    seq: int = Field(default=0, ge=0)
    timestamp: datetime = Field(default_factory=_utcnow)


# --- payloads ------------------------------------------------------------
# Payloads are explicit typed models. `plan`, `arguments` and
# `structured_output` are intentionally `dict[str, Any]` — they carry
# structured-but-arbitrary data (a plan document, tool arguments, tool
# output) whose shape is defined by the tool, not by this protocol.


class StatusPayload(BaseModel):
    status: str
    message: str | None = None


class PlanReviewRequiredPayload(BaseModel):
    checkpoint_id: str
    title: str
    plan: dict[str, Any]
    risk_level: str | None = None
    estimated_cost_usd: float | None = None


class ToolCallPayload(BaseModel):
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    permission_level: str | None = None
    approval_required: bool = False


class ToolObservationPayload(BaseModel):
    tool_call_id: str
    status: str
    summary: str
    structured_output: dict[str, Any] = Field(default_factory=dict)
    raw_output_ref: str | None = None
    error: str | None = None


class PaperFoundPayload(BaseModel):
    paper: Paper


class ClaimExtractedPayload(BaseModel):
    claim: Claim


class ArtifactCreatedPayload(BaseModel):
    artifact_id: str
    artifact_type: str
    path: str | None = None
    title: str | None = None


class ErrorPayload(BaseModel):
    message: str
    code: str | None = None
    recoverable: bool = True


class DonePayload(BaseModel):
    summary: str | None = None
    final_report_id: str | None = None


# --- typed events --------------------------------------------------------


class StatusEvent(ResearchEventBase):
    type: Literal["status"] = "status"
    payload: StatusPayload


class PlanReviewRequiredEvent(ResearchEventBase):
    type: Literal["plan_review_required"] = "plan_review_required"
    payload: PlanReviewRequiredPayload


class ToolCallEvent(ResearchEventBase):
    type: Literal["tool_call"] = "tool_call"
    payload: ToolCallPayload


class ToolObservationEvent(ResearchEventBase):
    type: Literal["tool_observation"] = "tool_observation"
    payload: ToolObservationPayload


class PaperFoundEvent(ResearchEventBase):
    type: Literal["paper_found"] = "paper_found"
    payload: PaperFoundPayload


class ClaimExtractedEvent(ResearchEventBase):
    type: Literal["claim_extracted"] = "claim_extracted"
    payload: ClaimExtractedPayload


class ArtifactCreatedEvent(ResearchEventBase):
    type: Literal["artifact_created"] = "artifact_created"
    payload: ArtifactCreatedPayload


class ErrorEvent(ResearchEventBase):
    type: Literal["error"] = "error"
    payload: ErrorPayload


class DoneEvent(ResearchEventBase):
    type: Literal["done"] = "done"
    payload: DonePayload


# --- discriminated union -------------------------------------------------


ResearchEvent = Annotated[
    Union[
        StatusEvent,
        PlanReviewRequiredEvent,
        ToolCallEvent,
        ToolObservationEvent,
        PaperFoundEvent,
        ClaimExtractedEvent,
        ArtifactCreatedEvent,
        ErrorEvent,
        DoneEvent,
    ],
    Field(discriminator="type"),
]
"""Discriminated union of every typed Research OS event, keyed on `type`."""

RESEARCH_EVENT_ADAPTER: TypeAdapter[Any] = TypeAdapter(ResearchEvent)
"""Validator for `ResearchEvent` — `validate_python` on any raw event dict."""

RESEARCH_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "status",
        "plan_review_required",
        "tool_call",
        "tool_observation",
        "paper_found",
        "claim_extracted",
        "artifact_created",
        "error",
        "done",
    }
)
"""Every event `type` string that has a typed variant in `ResearchEvent`."""
