"""API Pydantic schemas"""
from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    question: str = Field(..., min_length=10, max_length=500)
    user_id: str | None = None


class CreateTaskResponse(BaseModel):
    task_id: str
    stream_url: str


class ApproveRequest(BaseModel):
    action: Literal["approve", "modify", "reject"]
    modified_plan: list[str] | None = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["running", "finished", "failed"]
    current_node: str | None
    findings_count: int
    final_report: str | None