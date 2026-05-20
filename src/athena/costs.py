from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Awaitable, Callable

from athena.schemas import TokenUsage

PRICING_USD_PER_TOKEN: dict[str, tuple[float, float]] = {
    "mock-researcher": (0.0, 0.0),
    "gpt-4o-mini": (0.15 / 1_000_000, 0.60 / 1_000_000),
    "gpt-4o": (2.50 / 1_000_000, 10.00 / 1_000_000),
    "claude-3-5-haiku": (0.80 / 1_000_000, 4.00 / 1_000_000),
    "claude-3-5-sonnet": (3.00 / 1_000_000, 15.00 / 1_000_000),
    # Self-hosted / open-weight — no per-token cost (server-side GPU bill)
    "gemma-4-31B-it": (0.0, 0.0),
    "gemma-2-27b-it": (0.0, 0.0),
    "gemma-3-27b-it": (0.0, 0.0),
    # Google AI Studio (free tier rates approximated)
    "gemini-2.5-flash": (0.075 / 1_000_000, 0.30 / 1_000_000),
    "gemini-2.5-pro":   (1.25 / 1_000_000, 5.00 / 1_000_000),
}


@dataclass
class TokenLedger:
    budget_usd: float = 2.0
    spent_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    by_model: dict[str, float] = field(default_factory=dict)
    by_node: dict[str, float] = field(default_factory=dict)
    usage: list[TokenUsage] = field(default_factory=list)

    def add(self, model: str, node: str, input_tokens: int, output_tokens: int) -> TokenUsage:
        in_price, out_price = PRICING_USD_PER_TOKEN.get(model, (0.0, 0.0))
        cost = input_tokens * in_price + output_tokens * out_price
        self.spent_usd += cost
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.by_model[model] = self.by_model.get(model, 0.0) + cost
        self.by_node[node] = self.by_node.get(node, 0.0) + cost
        usage = TokenUsage(model=model, node=node, input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost)
        self.usage.append(usage)
        return usage

    @property
    def soft_exceeded(self) -> bool:
        return self.spent_usd > self.budget_usd * 0.8

    @property
    def hard_exceeded(self) -> bool:
        return self.spent_usd > self.budget_usd

    def snapshot(self) -> dict[str, Any]:
        return {
            "budget_usd": self.budget_usd,
            "spent_usd": round(self.spent_usd, 6),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "by_model": self.by_model,
            "by_node": self.by_node,
            "soft_exceeded": self.soft_exceeded,
            "hard_exceeded": self.hard_exceeded,
        }


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 3.2))


def guard_budget(node_name: str):
    """Decorator that accounts a node's LLM usage.

    Strategy:
      1. The decorated node may stash one or more real LLM results in
         `state.metadata['last_llm_calls']` while running. If present, this
         decorator records them with the actual model + token counts.
      2. Otherwise it falls back to a coarse text-length estimate (0-cost).
    """
    def decorator(func: Callable[..., Awaitable[Any]]):
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            state = args[0] if args else kwargs.get("state")
            ledger: TokenLedger = getattr(state, "metadata", {}).setdefault("ledger", TokenLedger())
            metadata = getattr(state, "metadata", {})
            metadata["last_llm_calls"] = []  # node will append entries
            result = await func(*args, **kwargs)
            calls: list[dict[str, Any]] = metadata.pop("last_llm_calls", []) or []
            if calls:
                for call in calls:
                    usage = ledger.add(
                        call.get("model") or "mock-researcher",
                        node_name,
                        int(call.get("input_tokens", 0) or 0),
                        int(call.get("output_tokens", 0) or 0),
                    )
                    if hasattr(state, "add_usage"):
                        state.add_usage(usage)
            else:
                before = estimate_tokens(str(getattr(state, "question", "")))
                after = estimate_tokens(str(result))
                usage = ledger.add("mock-researcher", node_name, before, after)
                if hasattr(state, "add_usage"):
                    state.add_usage(usage)
            return result
        return wrapper
    return decorator


def record_llm_call(state: Any, result: Any) -> None:
    """Helper for agent nodes to register a real LLM result with the budget decorator."""
    if not hasattr(state, "metadata") or result is None:
        return
    calls = state.metadata.setdefault("last_llm_calls", [])
    calls.append({
        "model": getattr(result, "model", None),
        "input_tokens": getattr(result, "input_tokens", 0),
        "output_tokens": getattr(result, "output_tokens", 0),
    })
