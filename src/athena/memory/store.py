from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class Feedback(BaseModel):
    id: str = Field(default_factory=lambda: f"fb_{uuid4().hex[:8]}")
    task_id: str
    rating: int = Field(ge=-1, le=1)
    comment: str = ""
    final_report: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AntiPattern(BaseModel):
    id: str = Field(default_factory=lambda: f"ap_{uuid4().hex[:8]}")
    pattern: str
    correction: str
    confidence: float = 0.5
    tags: list[str] = Field(default_factory=list)


@dataclass
class MemoryStore:
    feedback: list[Feedback] = field(default_factory=list)
    anti_patterns: list[AntiPattern] = field(default_factory=list)

    def add_feedback(self, feedback: Feedback) -> None:
        self.feedback.append(feedback)
        if feedback.rating < 0 and feedback.comment:
            self.anti_patterns.append(AntiPattern(
                pattern=feedback.comment[:180],
                correction="下次生成报告时优先补充用户指出的缺失维度,并在质量门控中显式检查。",
                confidence=0.55,
                tags=["user-feedback"],
            ))

    def retrieve(self, query: str, limit: int = 5) -> list[AntiPattern]:
        query_lower = query.lower()
        scored = []
        for item in self.anti_patterns:
            score = sum(1 for token in query_lower.split() if token in item.pattern.lower()) + item.confidence
            scored.append((score, item))
        return [item for _, item in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]]
