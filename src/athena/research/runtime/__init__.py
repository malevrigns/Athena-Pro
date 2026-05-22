"""Research OS agent runtime.

Phase 2 / roadmap section 7: the iterative agent loop that replaces the fixed
report pipeline.

- `loop.py`      — the iterative select-tool / execute / observe cycle
- `state.py`     — `ResearchRuntimeState`, the single business-state object
- `checkpoints.py` — durable, genuinely-blocking human review checkpoints
- `session.py`   — `ResearchSession`, the run orchestrator
"""

from __future__ import annotations

from .checkpoints import CheckpointService, checkpoint_approval_handler
from .loop import (
    AgentBrain,
    AgentLoop,
    AgentLoopResult,
    AgentStep,
    ApprovalAsk,
    ApprovalHandler,
    LLMAgentBrain,
    LoopContext,
    LoopLimits,
    LoopOutcome,
    LoopUsage,
    ScriptedBrain,
    StepRecord,
    StepUsage,
    auto_approve,
    deny_all_approvals,
)
from .session import PlanReviewOutcome, ResearchSession, SessionResult
from .state import ResearchRuntimeState, load_runtime_state

__all__ = [
    "AgentBrain",
    "AgentLoop",
    "AgentLoopResult",
    "AgentStep",
    "ApprovalAsk",
    "ApprovalHandler",
    "CheckpointService",
    "LLMAgentBrain",
    "LoopContext",
    "LoopLimits",
    "LoopOutcome",
    "LoopUsage",
    "PlanReviewOutcome",
    "ResearchRuntimeState",
    "ResearchSession",
    "ScriptedBrain",
    "SessionResult",
    "StepRecord",
    "StepUsage",
    "auto_approve",
    "checkpoint_approval_handler",
    "deny_all_approvals",
    "load_runtime_state",
]
