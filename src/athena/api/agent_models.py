from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


AgentStatus = Literal["queued", "running", "done", "skipped", "failed"]


@dataclass(frozen=True)
class AgentItemSpec:
    id: str
    role: str
    title: str
    status: AgentStatus
    objective: str
    input_summary: str
    output_summary: str
    nodes: list[str]
    event_types: list[str]


class AgentTraceItem(BaseModel):
    id: str
    role: str
    title: str
    status: AgentStatus
    objective: str
    input_summary: str = ""
    output_summary: str = ""
    evidence_count: int = 0
    source_count: int = 0
    knowledge_hits: int = 0
    token_count: int = 0
    cost_usd: float = 0.0
    autonomy_level: str = ""
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    next_action: str = ""
    updated_at: str = ""


class AgentTraceSummary(BaseModel):
    total_agents: int
    completed_agents: int
    running_agents: int
    queued_agents: int
    skipped_agents: int
    failed_agents: int
    source_count: int
    knowledge_hits: int
    total_tokens: int
    total_cost_usd: float
    capability_count: int
    tool_count: int


class AgentTraceResponse(BaseModel):
    items: list[AgentTraceItem]
    summary: AgentTraceSummary
