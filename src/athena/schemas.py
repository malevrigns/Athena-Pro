from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl


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
