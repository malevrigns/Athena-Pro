"""Iterative agent loop for the Research OS runtime (roadmap section 7.1).

This is the real agent loop the roadmap asks for — not a fixed pipeline. Each
iteration the *brain* (an LLM, or a scripted brain in tests) inspects the goal
and the observation history and decides to either call a tool or finish. Tool
calls go through the `ToolRouter` and `ApprovalPolicy`, so every call is typed,
validated, governed and recorded.

The loop owns the production safeguards from roadmap section 7.1:

- iteration / tool-call ceilings
- token and cost budgets
- tool-call validation (unknown tool, missing name)
- approval pause/resume (the injectable async `approval_handler` *is* the pause)
- error recovery (a failed tool becomes an observation, the loop continues)
- observation truncation
- context compaction (the brain sees a bounded transcript)
- loop-repetition / doom-loop detection
- cooperative cancellation

The LLM client in this project is text-only, so the brain protocol is a small
JSON contract rather than native tool calling; `LLMAgentBrain` adapts an
`LLMClient` to it and `ScriptedBrain` makes the loop deterministically testable.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from json import JSONDecoder
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from athena.llm_factory import LLMClient
from athena.research.governance.policy import ApprovalDecision, ApprovalPolicy
from athena.research.persistence import ResearchRepository
from athena.research.tools import (
    ToolCallRecord,
    ToolCallStatus,
    ToolObservationRecord,
    ToolObservationStatus,
    ToolRouter,
    utcnow,
)

# --- configuration -------------------------------------------------------


class LoopOutcome(StrEnum):
    """Why the loop stopped."""

    completed = "completed"
    max_iterations = "max_iterations"
    max_tool_calls = "max_tool_calls"
    token_budget_exceeded = "token_budget_exceeded"
    cost_budget_exceeded = "cost_budget_exceeded"
    cancelled = "cancelled"
    repetition_aborted = "repetition_aborted"
    error = "error"


class LoopLimits(BaseModel):
    """Hard ceilings that bound a single loop run (roadmap section 7.1)."""

    max_iterations: int = Field(default=12, ge=1)
    max_tool_calls: int = Field(default=24, ge=1)
    token_budget: int = Field(default=120_000, ge=1)
    cost_budget_usd: float = Field(default=5.0, ge=0)
    usd_per_1k_tokens: float = Field(default=0.0, ge=0)
    max_observation_chars: int = Field(default=4000, ge=200)
    repetition_threshold: int = Field(default=3, ge=2)
    context_message_limit: int = Field(default=40, ge=4)


# --- brain protocol ------------------------------------------------------


class StepUsage(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


class AgentStep(BaseModel):
    """One brain decision: call a tool, or finish with an answer."""

    kind: Literal["tool_call", "final"]
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    final_answer: str | None = None
    thought: str | None = None
    usage: StepUsage = Field(default_factory=StepUsage)


@dataclass(frozen=True)
class LoopContext:
    """The bounded view of the run handed to the brain each iteration."""

    goal: str
    tools: list[dict[str, Any]]
    transcript: list[str]
    iteration: int


class AgentBrain(Protocol):
    async def decide(self, context: LoopContext) -> AgentStep: ...


# --- approval ------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalAsk:
    tool_name: str
    arguments: dict[str, Any]
    decision: ApprovalDecision


# An approval handler may block (await human input) — that await is the loop's
# pause/resume point. The default denies, so an unattended loop is safe.
ApprovalHandler = Callable[[ApprovalAsk], Awaitable[bool]]


async def deny_all_approvals(_ask: ApprovalAsk) -> bool:
    return False


async def auto_approve(_ask: ApprovalAsk) -> bool:
    return True


# --- result --------------------------------------------------------------


class StepRecord(BaseModel):
    """A durable trace entry for one loop iteration."""

    index: int
    kind: str
    thought: str | None = None
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    approval_required: bool = False
    approval_granted: bool | None = None
    observation: str | None = None
    ok: bool | None = None
    error: str | None = None


class LoopUsage(BaseModel):
    iterations: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class AgentLoopResult(BaseModel):
    outcome: LoopOutcome
    final_answer: str | None = None
    usage: LoopUsage
    steps: list[StepRecord] = Field(default_factory=list)
    error: str | None = None


# --- the loop ------------------------------------------------------------


class AgentLoop:
    """Runs an agentic select-tool / execute / observe cycle until a stop condition."""

    def __init__(
        self,
        *,
        brain: AgentBrain,
        router: ToolRouter,
        policy: ApprovalPolicy | None = None,
        limits: LoopLimits | None = None,
        approval_handler: ApprovalHandler = deny_all_approvals,
        cancel: asyncio.Event | None = None,
        repository: ResearchRepository | None = None,
        task_id: str = "agent_loop",
        project_id: str | None = None,
    ) -> None:
        self._brain = brain
        self._router = router
        self._policy = policy or ApprovalPolicy()
        self._limits = limits or LoopLimits()
        self._approval_handler = approval_handler
        self._cancel = cancel
        self._repository = repository
        self._task_id = task_id
        self._project_id = project_id

    async def run(self, goal: str) -> AgentLoopResult:
        usage = LoopUsage()
        steps: list[StepRecord] = []
        transcript: list[str] = []
        signatures: Counter[str] = Counter()

        while True:
            stop = self._check_budgets(usage)
            if stop is not None:
                return self._result(stop, None, usage, steps)

            usage.iterations += 1
            context = LoopContext(
                goal=goal,
                tools=self._router.specs_for_llm(),
                transcript=_compact(transcript, self._limits.context_message_limit),
                iteration=usage.iterations,
            )
            try:
                step = await self._brain.decide(context)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - brain failures must not crash the loop
                return self._result(LoopOutcome.error, None, usage, steps, error=str(exc))

            self._accrue(usage, step.usage)

            if step.kind == "final":
                steps.append(
                    StepRecord(
                        index=usage.iterations,
                        kind="final",
                        thought=step.thought,
                        observation=step.final_answer,
                    )
                )
                return self._result(
                    LoopOutcome.completed, step.final_answer or "", usage, steps
                )

            signature = _signature(step.tool_name, step.arguments)
            signatures[signature] += 1
            if signatures[signature] >= self._limits.repetition_threshold:
                steps.append(
                    StepRecord(
                        index=usage.iterations,
                        kind="tool_call",
                        thought=step.thought,
                        tool_name=step.tool_name,
                        arguments=step.arguments,
                        ok=False,
                        error="loop_repetition",
                        observation="aborted: the same tool call was repeated",
                    )
                )
                return self._result(LoopOutcome.repetition_aborted, None, usage, steps)

            record = await self._run_tool_step(step, usage)
            record.index = usage.iterations
            steps.append(record)
            transcript.append(_transcript_line(record, self._limits.max_observation_chars))

    # -- internals --------------------------------------------------------

    def _check_budgets(self, usage: LoopUsage) -> LoopOutcome | None:
        if self._cancel is not None and self._cancel.is_set():
            return LoopOutcome.cancelled
        if usage.iterations >= self._limits.max_iterations:
            return LoopOutcome.max_iterations
        if usage.tool_calls >= self._limits.max_tool_calls:
            return LoopOutcome.max_tool_calls
        if usage.input_tokens + usage.output_tokens >= self._limits.token_budget:
            return LoopOutcome.token_budget_exceeded
        if self._limits.cost_budget_usd > 0 and usage.cost_usd >= self._limits.cost_budget_usd:
            return LoopOutcome.cost_budget_exceeded
        return None

    def _accrue(self, usage: LoopUsage, step_usage: StepUsage) -> None:
        usage.input_tokens += step_usage.input_tokens
        usage.output_tokens += step_usage.output_tokens
        usage.cost_usd = round(
            usage.cost_usd
            + step_usage.total / 1000 * self._limits.usd_per_1k_tokens,
            6,
        )

    async def _run_tool_step(self, step: AgentStep, usage: LoopUsage) -> StepRecord:
        record = StepRecord(
            index=0,
            kind="tool_call",
            thought=step.thought,
            tool_name=step.tool_name,
            arguments=step.arguments,
        )

        # tool-call validation
        if not step.tool_name:
            record.ok = False
            record.error = "missing_tool_name"
            record.observation = "invalid tool call: no tool name was provided"
            return record
        try:
            spec = self._router.get(step.tool_name)
        except KeyError:
            record.ok = False
            record.error = "unknown_tool"
            record.observation = f"invalid tool call: unknown tool '{step.tool_name}'"
            return record

        # approval gate (pause/resume)
        decision = self._policy.check_tool_call(spec, step.arguments)
        if decision.required or not decision.allowed:
            record.approval_required = True
            granted = (
                False
                if not decision.allowed
                else await self._approval_handler(
                    ApprovalAsk(step.tool_name, step.arguments, decision)
                )
            )
            record.approval_granted = granted
            if not granted:
                record.ok = False
                record.error = "approval_denied"
                record.observation = f"approval denied: {decision.reason or decision.risk_level}"
                await self._persist(record, spec.permission_level, approved=False)
                return record

        # execution + error recovery
        usage.tool_calls += 1
        result = await self._router.execute(step.tool_name, step.arguments)
        record.ok = result.ok
        record.error = result.error
        record.observation = _truncate(
            _observation_text(result.summary, result.structured_output),
            self._limits.max_observation_chars,
        )
        await self._persist(record, spec.permission_level, approved=record.approval_granted)
        return record

    async def _persist(
        self,
        record: StepRecord,
        permission_level: Any,
        *,
        approved: bool | None,
    ) -> None:
        """Mirror an executed step into the durable tool-call trace tables."""
        if self._repository is None:
            return
        now = utcnow()
        if approved is None:
            approval_status = "not_required"
        else:
            approval_status = "approved" if approved else "denied"
        executed = record.error != "approval_denied"
        call = ToolCallRecord(
            task_id=self._task_id,
            project_id=self._project_id,
            tool_name=record.tool_name or "",
            arguments=record.arguments,
            permission_level=permission_level,
            approval_status=approval_status,
            status=ToolCallStatus.completed if record.ok else ToolCallStatus.failed,
            started_at=now if executed else None,
            finished_at=now if executed else None,
        )
        await self._repository.record_tool_call(call)
        await self._repository.record_tool_observation(
            ToolObservationRecord(
                tool_call_id=call.id,
                status=ToolObservationStatus.ok if record.ok else ToolObservationStatus.error,
                summary=record.observation or "",
                error=record.error,
            )
        )

    def _result(
        self,
        outcome: LoopOutcome,
        final_answer: str | None,
        usage: LoopUsage,
        steps: list[StepRecord],
        *,
        error: str | None = None,
    ) -> AgentLoopResult:
        return AgentLoopResult(
            outcome=outcome,
            final_answer=final_answer,
            usage=usage,
            steps=steps,
            error=error,
        )


# --- brains --------------------------------------------------------------


@dataclass
class ScriptedBrain:
    """A deterministic brain for tests: replays a fixed list of steps.

    Once the script is exhausted it returns a `final` step, so a loop driven by
    a ScriptedBrain always terminates instead of hanging.
    """

    steps: list[AgentStep]
    _cursor: int = 0

    async def decide(self, _context: LoopContext) -> AgentStep:
        if self._cursor >= len(self.steps):
            return AgentStep(kind="final", final_answer="(script exhausted)")
        step = self.steps[self._cursor]
        self._cursor += 1
        return step


@dataclass
class LLMAgentBrain:
    """Adapts a text-only `LLMClient` to the JSON brain contract."""

    llm: LLMClient
    node: str = "researcher"

    async def decide(self, context: LoopContext) -> AgentStep:
        prompt = _build_brain_prompt(context)
        result = await self.llm.complete_full(prompt, node=self.node)
        usage = StepUsage(input_tokens=result.input_tokens, output_tokens=result.output_tokens)
        return _parse_step(result.text, usage)


# --- helpers -------------------------------------------------------------


def _build_brain_prompt(context: LoopContext) -> str:
    tool_lines = [
        f"- {tool['function']['name']}: {tool['function']['description']}"
        for tool in context.tools
    ]
    history = "\n".join(context.transcript) if context.transcript else "(no actions yet)"
    return (
        "You are an autonomous research agent. Work towards the goal one step "
        "at a time by calling a tool, or finish when the goal is met.\n\n"
        f"## Goal\n{context.goal}\n\n"
        f"## Available tools\n{chr(10).join(tool_lines) or '(none)'}\n\n"
        f"## History\n{history}\n\n"
        "## Respond\n"
        "Reply with exactly one JSON object and nothing else:\n"
        '{"action": "tool_call", "tool": "<name>", "arguments": {...}, "thought": "<why>"}\n'
        "or\n"
        '{"action": "final", "answer": "<final answer>", "thought": "<why>"}'
    )


def _parse_step(text: str, usage: StepUsage) -> AgentStep:
    data = _extract_json_object(text)
    if data is None:
        # A non-JSON reply is treated as a prose final answer rather than an
        # error, so a loop never hangs on a model that ignored the contract.
        return AgentStep(kind="final", final_answer=(text or "").strip(), usage=usage)
    action = str(data.get("action", "")).strip()
    if action == "tool_call":
        arguments = data.get("arguments")
        return AgentStep(
            kind="tool_call",
            tool_name=data.get("tool") or data.get("tool_name"),
            arguments=arguments if isinstance(arguments, dict) else {},
            thought=data.get("thought"),
            usage=usage,
        )
    return AgentStep(
        kind="final",
        final_answer=str(data.get("answer", "")).strip() or None,
        thought=data.get("thought"),
        usage=usage,
    )


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = (text or "").strip()
    if not stripped:
        return None
    decoder = JSONDecoder()
    starts = [index for index, char in enumerate(stripped) if char == "{"]
    for start in starts:
        try:
            value, _ = decoder.raw_decode(stripped[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _signature(tool_name: str | None, arguments: dict[str, Any]) -> str:
    return json.dumps([tool_name, arguments], sort_keys=True, default=str)


def _observation_text(summary: str, structured: dict[str, Any]) -> str:
    if not structured:
        return summary
    return f"{summary} | {json.dumps(structured, ensure_ascii=False, default=str)}"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _transcript_line(record: StepRecord, observation_limit: int) -> str:
    args = _truncate(json.dumps(record.arguments, ensure_ascii=False, default=str), 300)
    status = "ok" if record.ok else "error"
    observation = _truncate(record.observation or "", observation_limit)
    return f"[{record.index}] tool={record.tool_name} args={args} -> {status}: {observation}"


def _compact(transcript: list[str], limit: int) -> list[str]:
    """Bound the history shown to the brain: keep the first and most recent
    entries and elide the middle with a marker (roadmap section 7.1)."""
    if len(transcript) <= limit:
        return list(transcript)
    head = 1
    tail = limit - head - 1
    elided = len(transcript) - head - tail
    return [
        *transcript[:head],
        f"[... {elided} earlier steps elided for context compaction ...]",
        *transcript[-tail:],
    ]
