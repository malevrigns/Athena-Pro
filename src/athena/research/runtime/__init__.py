"""Research OS agent runtime.

Phase 2 / roadmap section 7: the iterative agent loop that replaces the fixed
report pipeline. `loop.py` is the entry point; later work adds session and
checkpoint orchestration around it.
"""

from __future__ import annotations

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

__all__ = [
    "AgentBrain",
    "AgentLoop",
    "AgentLoopResult",
    "AgentStep",
    "ApprovalAsk",
    "ApprovalHandler",
    "LLMAgentBrain",
    "LoopContext",
    "LoopLimits",
    "LoopOutcome",
    "LoopUsage",
    "ScriptedBrain",
    "StepRecord",
    "StepUsage",
    "auto_approve",
    "deny_all_approvals",
]
