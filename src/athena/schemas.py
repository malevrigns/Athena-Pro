from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    WAITING_REVIEW = "waiting_review"
    RESEARCHING = "researching"
    QUALITY_GATE = "quality_gate"
    WRITING = "writing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    DONE = "done"
    FAILED = "failed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Scope(str, Enum):
    ONCE = "once"
    SESSION = "session"
    ALWAYS = "always"


class Source(BaseModel):
    id: str = Field(default_factory=lambda: f"src_{uuid4().hex[:8]}")
    title: str
    url: str
    snippet: str = ""
    retrieved_at: datetime = Field(default_factory=utcnow)
    credibility: float = Field(default=0.7, ge=0, le=1)
    source_type: Literal["web", "paper", "news", "internal", "mock"] = "web"


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: f"finding_{uuid4().hex[:8]}")
    topic_id: str
    title: str
    summary: str
    evidence: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0, le=1)
    created_at: datetime = Field(default_factory=utcnow)


class ResearchTopic(BaseModel):
    id: str = Field(default_factory=lambda: f"topic_{uuid4().hex[:6]}")
    title: str
    question: str
    rationale: str = ""
    search_queries: list[str] = Field(default_factory=list)
    priority: int = Field(default=1, ge=1, le=5)


class ResearchPlan(BaseModel):
    id: str = Field(default_factory=lambda: f"plan_{uuid4().hex[:8]}")
    question: str
    topics: list[ResearchTopic]
    assumptions: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    estimated_cost_usd: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)


class ReviewDecision(BaseModel):
    approved: bool
    reviewer: str = "human"
    comments: str = ""
    revised_topics: list[ResearchTopic] | None = None
    created_at: datetime = Field(default_factory=utcnow)


class QualityScore(BaseModel):
    factuality: float = Field(default=0.0, ge=0, le=1)
    coverage: float = Field(default=0.0, ge=0, le=1)
    citation_integrity: float = Field(default=0.0, ge=0, le=1)
    contradiction_risk: float = Field(default=0.0, ge=0, le=1)
    overall: float = Field(default=0.0, ge=0, le=1)
    notes: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    number: int
    source_id: str
    title: str
    url: str
    quote: str = ""
    accessed_at: datetime = Field(default_factory=utcnow)


class FinalReport(BaseModel):
    task_id: str
    title: str
    markdown: str
    citations: list[Citation] = Field(default_factory=list)
    quality: QualityScore | None = None
    generated_at: datetime = Field(default_factory=utcnow)


class PermissionRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"perm_{uuid4().hex[:8]}")
    task_id: str
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    reason: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class PermissionDecision(BaseModel):
    request_id: str
    approved: bool
    scope: Scope = Scope.ONCE
    decided_by: str = "human"
    comment: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class TokenUsage(BaseModel):
    model: str
    node: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class TaskSnapshot(BaseModel):
    id: str
    question: str
    user_id: str = "demo-user"
    status: TaskStatus = TaskStatus.CREATED
    plan: ResearchPlan | None = None
    findings: list[Finding] = Field(default_factory=list)
    final_report: FinalReport | None = None
    quality: QualityScore | None = None
    cost_usd: float = 0.0
    events_count: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class StreamEvent(BaseModel):
    seq: int = 0
    type: str
    task_id: str
    node: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=utcnow)

    def sse(self) -> str:
        return "data: " + self.model_dump_json() + "\n\n"


# ============================================================
# Typed event protocol
# ------------------------------------------------------------
# `StreamEvent` above is the loose runtime carrier mutated while a graph runs.
# The models below are the authoritative, validated event protocol: every
# event the backend emits is one variant of `AthenaEvent`, discriminated on
# `type`. The frontend Zod discriminated union (web/src/types/api.ts) mirrors
# this 1:1 and is kept in sync by hand.
# ============================================================


class _TypedEvent(BaseModel):
    """Shared envelope for every typed event variant."""

    seq: int = 0
    task_id: str
    node: str | None = None
    ts: datetime = Field(default_factory=utcnow)


class _Payload(BaseModel):
    """Base for event payloads — tolerant of extra keys so the protocol can
    evolve without breaking peers on a different revision."""

    model_config = ConfigDict(extra="allow")


class CreatedPayload(_Payload):
    question: str = ""


class StatusPayload(_Payload):
    status: str = ""
    updated_at: str | None = None


class PlanPayload(_Payload):
    plan: dict[str, Any] = Field(default_factory=dict)


class PlanExpandedPayload(_Payload):
    new_topics: list[dict[str, Any]] = Field(default_factory=list)


class FindingPayload(_Payload):
    finding: dict[str, Any] = Field(default_factory=dict)


class QualityPayload(_Payload):
    quality: dict[str, Any] = Field(default_factory=dict)


class ReviewPayload(_Payload):
    review: str = ""


class RoutePayload(_Payload):
    iteration: int = 0
    route: str = ""
    quality: float | None = None
    finding_count: int = 0
    topic_count: int = 0


class DonePayload(_Payload):
    final_report: dict[str, Any] = Field(default_factory=dict)


class UsagePayload(_Payload):
    usage: dict[str, Any] = Field(default_factory=dict)


class CancelledPayload(_Payload):
    reason: str = ""


class ErrorPayload(_Payload):
    error: str = ""


class WarningPayload(_Payload):
    message: str = ""


class ReviewRequiredPayload(_Payload):
    stage: str = "plan"
    topic_count: int = 0
    message: str = ""


class ReviewApprovedPayload(_Payload):
    comments: str = ""


class CitationReviewPayload(_Payload):
    mode: str = "manual"          # manual | auto | empty
    total: int = 0
    pending: int = 0
    model: str = ""
    message: str = ""
    flag: int = 0
    reject: int = 0
    # The auto-mode `pass` count arrives as an extra key (`pass` is a keyword).


class CreatedEvent(_TypedEvent):
    type: Literal["created"] = "created"
    payload: CreatedPayload = Field(default_factory=CreatedPayload)


class StatusEvent(_TypedEvent):
    type: Literal["status"] = "status"
    payload: StatusPayload = Field(default_factory=StatusPayload)


class PlanEvent(_TypedEvent):
    type: Literal["plan"] = "plan"
    payload: PlanPayload = Field(default_factory=PlanPayload)


class PlanExpandedEvent(_TypedEvent):
    type: Literal["plan_expanded"] = "plan_expanded"
    payload: PlanExpandedPayload = Field(default_factory=PlanExpandedPayload)


class FindingEvent(_TypedEvent):
    type: Literal["finding"] = "finding"
    payload: FindingPayload = Field(default_factory=FindingPayload)


class QualityEvent(_TypedEvent):
    type: Literal["quality"] = "quality"
    payload: QualityPayload = Field(default_factory=QualityPayload)


class ReviewEvent(_TypedEvent):
    type: Literal["review"] = "review"
    payload: ReviewPayload = Field(default_factory=ReviewPayload)


class RouteEvent(_TypedEvent):
    type: Literal["route"] = "route"
    payload: RoutePayload = Field(default_factory=RoutePayload)


class DoneEvent(_TypedEvent):
    type: Literal["done"] = "done"
    payload: DonePayload = Field(default_factory=DonePayload)


class UsageEvent(_TypedEvent):
    type: Literal["usage"] = "usage"
    payload: UsagePayload = Field(default_factory=UsagePayload)


class CancelledEvent(_TypedEvent):
    type: Literal["cancelled"] = "cancelled"
    payload: CancelledPayload = Field(default_factory=CancelledPayload)


class ErrorEvent(_TypedEvent):
    type: Literal["error"] = "error"
    payload: ErrorPayload = Field(default_factory=ErrorPayload)


class WarningEvent(_TypedEvent):
    type: Literal["warning"] = "warning"
    payload: WarningPayload = Field(default_factory=WarningPayload)


class ReviewRequiredEvent(_TypedEvent):
    type: Literal["review_required"] = "review_required"
    payload: ReviewRequiredPayload = Field(default_factory=ReviewRequiredPayload)


class ReviewApprovedEvent(_TypedEvent):
    type: Literal["review_approved"] = "review_approved"
    payload: ReviewApprovedPayload = Field(default_factory=ReviewApprovedPayload)


class CitationReviewEvent(_TypedEvent):
    type: Literal["citation_review"] = "citation_review"
    payload: CitationReviewPayload = Field(default_factory=CitationReviewPayload)


AthenaEvent = Annotated[
    Union[
        CreatedEvent, StatusEvent, PlanEvent, PlanExpandedEvent, FindingEvent,
        QualityEvent, ReviewEvent, RouteEvent, DoneEvent, UsageEvent,
        CancelledEvent, ErrorEvent, WarningEvent, ReviewRequiredEvent,
        ReviewApprovedEvent, CitationReviewEvent,
    ],
    Field(discriminator="type"),
]
"""Discriminated union of every event the backend emits."""

ATHENA_EVENT_ADAPTER: TypeAdapter[Any] = TypeAdapter(AthenaEvent)
"""Validator for `AthenaEvent` — `validate_python` on any raw event dict."""

# Every event `type` that has a typed variant in `AthenaEvent`.
EVENT_TYPES: frozenset[str] = frozenset({
    "created", "status", "plan", "plan_expanded", "finding", "quality",
    "review", "route", "done", "usage", "cancelled", "error", "warning",
    "review_required", "review_approved", "citation_review",
})
