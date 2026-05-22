"""Tool protocol primitives for the Research OS runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class PermissionLevel(StrEnum):
    read_only = "read_only"
    network_read = "network_read"
    write_artifact = "write_artifact"
    write_repo = "write_repo"
    run_local_command = "run_local_command"
    run_expensive_job = "run_expensive_job"
    external_side_effect = "external_side_effect"
    destructive = "destructive"


class ToolCallStatus(StrEnum):
    pending = "pending"
    waiting_approval = "waiting_approval"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class ToolObservationStatus(StrEnum):
    ok = "ok"
    error = "error"
    skipped = "skipped"


class ToolResult(BaseModel):
    ok: bool
    summary: str
    structured_output: dict[str, Any] = Field(default_factory=dict)
    raw_output_ref: str | None = None
    error: str | None = None


class ToolCallRecord(BaseModel):
    id: str = Field(default_factory=lambda: _id("tc"))
    task_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None
    permission_level: PermissionLevel = PermissionLevel.read_only
    approval_status: str = "not_required"
    status: ToolCallStatus = ToolCallStatus.pending
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ToolObservationRecord(BaseModel):
    id: str = Field(default_factory=lambda: _id("obs"))
    tool_call_id: str
    status: ToolObservationStatus = ToolObservationStatus.ok
    summary: str
    structured_output: dict[str, Any] = Field(default_factory=dict)
    raw_output_ref: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class ToolTraceItem(BaseModel):
    call: ToolCallRecord
    observations: list[ToolObservationRecord] = Field(default_factory=list)


ToolHandler = Callable[[dict[str, Any]], Awaitable[ToolResult] | ToolResult]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: ToolHandler = field(repr=False)
    permission_level: PermissionLevel = PermissionLevel.read_only
    timeout_seconds: float = 30.0
    cost_level: str = "low"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("tool name is required")
        if not self.description:
            raise ValueError("tool description is required")
        if self.timeout_seconds <= 0:
            raise ValueError("tool timeout must be positive")
