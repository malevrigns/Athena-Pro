from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from athena.schemas import PermissionDecision, ReviewDecision, TaskSnapshot


class CreateTaskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=2000)
    user_id: str = "demo-user"


class CreateTaskResponse(BaseModel):
    task_id: str
    stream_url: str
    snapshot: TaskSnapshot


class InterruptResponse(BaseModel):
    task_id: str
    interrupted: bool


class ReviewRequest(ReviewDecision):
    task_id: str


class PermissionDecisionRequest(PermissionDecision):
    task_id: str
    tool_name: str


class ConfigSnapshot(BaseModel):
    env: str
    llm_provider: str
    default_model: str
    search_provider: str
    quality_threshold: float
    max_research_iterations: int
    max_budget_usd: float
    require_auth: bool
    export_formats: dict[str, bool]
    has_openai_key: bool
    has_anthropic_key: bool
    has_tavily_key: bool
    has_gemma_key: bool = False


class FeedbackRequest(BaseModel):
    task_id: str
    rating: int = Field(ge=-1, le=1)
    comment: str = ""


class ExportResponse(BaseModel):
    task_id: str
    format: str
    filename: str
    bytes: int
    download_url: str


class HealthResponse(BaseModel):
    ok: bool
    version: str
    uptime_sec: float
    llm_provider: str
    search_provider: str
    db_path: str
    extras: dict[str, Any] = Field(default_factory=dict)
