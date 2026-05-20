from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from athena.schemas import (
    Finding,
    FinalReport,
    PermissionRequest,
    QualityScore,
    ResearchPlan,
    StreamEvent,
    TaskStatus,
    TokenUsage,
    utcnow,
)


@dataclass
class ResearchState:
    """Runtime state used by both LangGraph and the fallback runner.

    The dataclass mirrors the TypedDict shape shown in the tutorial, but keeps default factories and
    helper methods. When LangGraph is installed, `graph/main_graph.py` converts this shape to a
    LangGraph StateGraph-compatible dictionary.
    """

    task_id: str
    question: str
    user_id: str = "demo-user"
    status: TaskStatus = TaskStatus.CREATED
    plan: ResearchPlan | None = None
    findings: list[Finding] = field(default_factory=list)
    permission_requests: list[PermissionRequest] = field(default_factory=list)
    quality: QualityScore | None = None
    final_report: FinalReport | None = None
    token_usage: list[TokenUsage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    events: list[StreamEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_event(self, event_type: str, node: str | None = None, **payload: Any) -> StreamEvent:
        event = StreamEvent(type=event_type, task_id=self.task_id, node=node, payload=payload)
        self.events.append(event)
        return event

    def set_status(self, status: TaskStatus, node: str | None = None) -> StreamEvent:
        self.status = status
        return self.add_event("status", node=node, status=status.value, updated_at=utcnow().isoformat())

    def add_finding(self, finding: Finding) -> None:
        self.findings.append(finding)
        self.add_event("finding", node="researcher", finding=finding.model_dump(mode="json"))

    def add_usage(self, usage: TokenUsage) -> None:
        self.token_usage.append(usage)
        self.add_event("usage", node=usage.node, usage=usage.model_dump(mode="json"))

    def add_error(self, error: str, node: str | None = None) -> None:
        self.errors.append(error)
        self.add_event("error", node=node, error=error)

    def to_snapshot(self):
        from athena.schemas import TaskSnapshot
        return TaskSnapshot(
            id=self.task_id,
            question=self.question,
            user_id=self.user_id,
            status=self.status,
            plan=self.plan,
            findings=self.findings,
            final_report=self.final_report,
            quality=self.quality,
            cost_usd=sum(u.cost_usd for u in self.token_usage),
            events_count=len(self.events),
        )


def merge_state(old: ResearchState, patch: dict[str, Any]) -> ResearchState:
    """Reducer-like merge helper used by tests and fallback runtime."""
    for key, value in patch.items():
        if key == "findings":
            old.findings.extend(value)
        elif key == "events":
            old.events.extend(value)
        elif key == "errors":
            old.errors.extend(value)
        elif hasattr(old, key):
            setattr(old, key, value)
    return old
