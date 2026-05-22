from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass
from typing import Protocol

from athena.config import get_settings
from athena.observability import logger


class LLMResult:
    __slots__ = ("text", "input_tokens", "output_tokens", "model")

    def __init__(self, text: str, input_tokens: int = 0, output_tokens: int = 0, model: str = "") -> None:
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model


class LLMClient(Protocol):
    async def complete(self, prompt: str, *, node: str) -> str: ...
    async def complete_full(self, prompt: str, *, node: str) -> LLMResult: ...


@dataclass
class MockLLM:
    """Deterministic model for offline demos and tests."""

    latency_sec: float = 0.03

    async def complete(self, prompt: str, *, node: str) -> str:
        return (await self.complete_full(prompt, node=node)).text

    async def complete_full(self, prompt: str, *, node: str) -> LLMResult:
        await asyncio.sleep(self.latency_sec)
        digest = hashlib.sha1(prompt.encode()).hexdigest()[:8]
        if node == "planner":
            text = (
                "我已经把问题拆成生态、技术、商业落地与风险治理四个角度,"
                "每个角度会并行去查询公开资料和企业案例,最终交叉验证。"
                f" #{digest}"
            )
        elif node == "writer":
            text = (
                "## 摘要\n这份报告基于多个公开来源,综合给出趋势判断与可执行建议。"
                "在 mock 模式下内容用于演示;接入真实 LLM 后会自动生成结构化长文。"
                f"\n\n_seed_ #{digest}"
            )
        elif node == "reviewer":
            text = "审阅意见: 总体证据充足,可再补充 1-2 个对比案例与最新一年的数据。"
        elif node == "researcher":
            text = (
                "结合上述来源,该方向已经从原型走向工程化,核心约束依然是评估与成本。"
                f" #{digest}"
            )
        else:
            text = f"{node} 已完成分析。证据摘要编号 #{digest}。"
        return LLMResult(text=text, input_tokens=max(1, len(prompt) // 4), output_tokens=max(1, len(text) // 4), model="mock-researcher")


@dataclass
class RawHttpLLM:
    """OpenAI-compatible /chat/completions caller using raw httpx.

    Differs from OpenAICompatibleLLM in that the Authorization header is only
    sent when an api_key is explicitly provided — required for self-hosted
    vLLM / TGI deployments that reject any Authorization header.
    """
    model: str
    base_url: str
    api_key: str | None = None
    timeout: int = 60
    temperature: float = 0.2

    async def complete(self, prompt: str, *, node: str) -> str:
        return (await self.complete_full(prompt, node=node)).text

    async def complete_full(self, prompt: str, *, node: str) -> LLMResult:
        import httpx
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": _system_prompt(node)},
                {"role": "user", "content": prompt},
            ],
        }
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        # Self-hosted vLLM is almost always on an internal network. Skip the
        # ambient HTTP/SOCKS proxy that httpx would otherwise pick up from the
        # environment, which would route requests to an external proxy that
        # cannot reach the private endpoint.
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except Exception as exc:
            logger.warning("llm.raw_http_error url=%s node=%s err=%s", url, node, exc)
            raise
        if resp.status_code >= 400:
            logger.warning("llm.raw_http_bad_status url=%s status=%s body=%s", url, resp.status_code, resp.text[:200])
            resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        text = ""
        if choices:
            text = choices[0].get("message", {}).get("content") or ""
        usage = data.get("usage") or {}
        return LLMResult(
            text=text,
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            model=self.model,
        )


@dataclass
class OpenAICompatibleLLM:
    """Works with OpenAI, DeepSeek, OpenRouter, vLLM, and any other OpenAI-compatible endpoint."""
    model: str
    api_key: str
    base_url: str | None = None
    timeout: int = 60
    temperature: float = 0.2

    async def complete(self, prompt: str, *, node: str) -> str:
        return (await self.complete_full(prompt, node=node)).text

    async def complete_full(self, prompt: str, *, node: str) -> LLMResult:
        try:
            from openai import AsyncOpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Install the `openai` package to use OpenAICompatibleLLM") from exc
        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)
        try:
            resp = await client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": _system_prompt(node)},
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception as exc:
            logger.warning("llm.openai_compat_error model=%s node=%s err=%s", self.model, node, exc)
            raise
        choice = resp.choices[0].message.content if resp.choices else ""
        usage = getattr(resp, "usage", None)
        return LLMResult(
            text=choice or "",
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            model=self.model,
        )


@dataclass
class AnthropicLLM:
    model: str
    api_key: str
    timeout: int = 60
    temperature: float = 0.2
    max_tokens: int = 2048

    async def complete(self, prompt: str, *, node: str) -> str:
        return (await self.complete_full(prompt, node=node)).text

    async def complete_full(self, prompt: str, *, node: str) -> LLMResult:
        try:
            from anthropic import AsyncAnthropic  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Install the `anthropic` package to use AnthropicLLM") from exc
        client = AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)
        try:
            resp = await client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=_system_prompt(node),
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.warning("llm.anthropic_error model=%s node=%s err=%s", self.model, node, exc)
            raise
        text_parts: list[str] = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(getattr(block, "text", ""))
        usage = getattr(resp, "usage", None)
        return LLMResult(
            text="\n".join(text_parts),
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            model=self.model,
        )


def _system_prompt(node: str) -> str:
    try:
        from athena.research.prompt_assets import load_research_node_prompt

        return load_research_node_prompt(node).text
    except Exception as exc:
        logger.debug("llm.prompt_asset_fallback node=%s err=%s", node, exc)

    base = (
        "你是 Athena Pro 的多 Agent 深度研究助手的一部分。"
        "严格使用中文输出,语气专业、克制、可被引用。"
    )
    role = {
        "planner": "你的角色是 Planner: 把用户问题拆成 3-5 个可并行调研的 topic,每个 topic 都要给出 rationale 与 search_queries。",
        "researcher": "你的角色是 Researcher: 基于给定主题做事实陈述,所有结论必须可以追溯到来源。",
        "reviewer": "你的角色是 Reviewer: 审阅 findings 的覆盖度、矛盾点和数据新鲜度,给出 1-3 条具体改进建议。",
        "writer": "你的角色是 Writer: 输出 Markdown 报告,使用清晰的小节、有序的关键结论、以及 [n] 形式的引用编号。",
        "quality_gate": "你的角色是 Quality Gate: 给 findings 打分,分别评估事实性、覆盖度、引用完整性。",
        "citation_review": "你的角色是 Citation Reviewer: 核对单条引用来源的可靠性、相关性与时效性,严格按要求只输出 JSON。",
    }.get(node, "")
    return f"{base}\n{role}"


def _build_client() -> LLMClient:
    settings = get_settings()
    provider = settings.llm_provider
    if provider == "mock" or settings.default_model.startswith("mock"):
        return MockLLM()
    temperature = settings.llm_temperature
    timeout = settings.llm_timeout_sec
    if provider == "openai":
        api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("llm.no_openai_key — falling back to mock")
            return MockLLM()
        return OpenAICompatibleLLM(settings.default_model, api_key, settings.openai_base_url, timeout, temperature)
    if provider == "anthropic":
        api_key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("llm.no_anthropic_key — falling back to mock")
            return MockLLM()
        return AnthropicLLM(settings.default_model, api_key, timeout, temperature)
    if provider == "deepseek":
        api_key = settings.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            logger.warning("llm.no_deepseek_key — falling back to mock")
            return MockLLM()
        return OpenAICompatibleLLM(settings.default_model, api_key, "https://api.deepseek.com", timeout, temperature)
    if provider == "openrouter":
        api_key = settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.warning("llm.no_openrouter_key — falling back to mock")
            return MockLLM()
        return OpenAICompatibleLLM(settings.default_model, api_key, "https://openrouter.ai/api/v1", timeout, temperature)
    if provider in {"gemma", "gemini"}:
        # Two supported topologies:
        #   1. Google AI Studio OpenAI-compatible endpoint (default).
        #      Docs: https://ai.google.dev/gemini-api/docs/openai
        #   2. Self-hosted vLLM / TGI / Ollama on a private base URL.
        #      Use ATHENA_GEMMA_BASE_URL (or legacy GBA_LLM_ENDPOINT) to point at it.
        base_url = (
            settings.gemma_base_url
            or os.getenv("GBA_LLM_ENDPOINT")
            or "https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        api_key = (
            settings.gemma_api_key
            or settings.google_api_key
            or os.getenv("GEMMA_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GBA_LLM_API_KEY")
        )
        # Pass the key through verbatim — many self-hosted vLLM instances are
        # started with `--api-key EMPTY` and require the literal string EMPTY
        # as the Bearer token. Only treat NULL / empty string as "no auth".
        if api_key == "":
            api_key = None
        model = os.getenv("GBA_LLM_MODEL") or settings.default_model
        # Self-hosted base urls almost always require no auth header. Use the
        # raw httpx caller so we have full header control.
        if settings.gemma_base_url or os.getenv("GBA_LLM_ENDPOINT") or base_url.startswith("http://"):
            return RawHttpLLM(model, base_url, api_key, timeout, temperature)
        # Google AI Studio path still needs an API key in Authorization.
        if not api_key:
            logger.warning("llm.no_google_key — falling back to mock (set ATHENA_GEMMA_API_KEY)")
            return MockLLM()
        return OpenAICompatibleLLM(model, api_key, base_url, timeout, temperature)
    logger.warning("llm.unknown_provider=%s — falling back to mock", provider)
    return MockLLM()


_client: LLMClient | None = None


def get_llm(node: str | None = None) -> LLMClient:
    """Return the default LLM client. Node-specific overrides can be supported by reading
    `settings.resolve_model(node)` and constructing a per-node client when needed."""
    global _client
    settings = get_settings()
    if node is not None:
        override_model = settings.resolve_model(node)
        if override_model and override_model != settings.default_model:
            return _build_for_model(override_model)
    if _client is None:
        _client = _build_client()
    return _client


def _build_for_model(model: str) -> LLMClient:
    settings = get_settings()
    provider = settings.llm_provider
    if provider == "mock":
        return MockLLM()
    if provider == "anthropic":
        api_key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY") or ""
        return AnthropicLLM(model, api_key, settings.llm_timeout_sec, settings.llm_temperature)
    base_url = settings.openai_base_url
    api_key = settings.openai_api_key or ""
    if provider == "deepseek":
        api_key = settings.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY") or ""
        base_url = "https://api.deepseek.com"
    elif provider == "openrouter":
        api_key = settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY") or ""
        base_url = "https://openrouter.ai/api/v1"
    elif provider in {"gemma", "gemini"}:
        api_key = (
            settings.gemma_api_key
            or settings.google_api_key
            or os.getenv("GEMMA_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GBA_LLM_API_KEY")
        )
        if api_key == "":
            api_key = None
        base_url = (
            settings.gemma_base_url
            or os.getenv("GBA_LLM_ENDPOINT")
            or "https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        # Self-hosted endpoints (custom base URL or plain HTTP) skip auth header.
        if settings.gemma_base_url or os.getenv("GBA_LLM_ENDPOINT") or base_url.startswith("http://"):
            return RawHttpLLM(model, base_url, api_key, settings.llm_timeout_sec, settings.llm_temperature)
    if not api_key:
        return MockLLM()
    return OpenAICompatibleLLM(model, api_key, base_url, settings.llm_timeout_sec, settings.llm_temperature)


def build_verifier_llm(
    provider: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
    *,
    timeout: int = 60,
    temperature: float = 0.0,
) -> LLMClient:
    """Build a standalone LLM client for citation verification.

    Independent of the global research-model settings: the citation reviewer
    can point at an entirely separate provider / key / endpoint.
    """
    provider = (provider or "mock").strip().lower()
    model = (model or "").strip()
    api_key = (api_key or "").strip()
    base_url = (base_url or "").strip()
    if provider == "mock" or not model:
        return MockLLM()
    if provider == "anthropic":
        if not api_key:
            logger.warning("verifier.no_anthropic_key — falling back to mock")
            return MockLLM()
        return AnthropicLLM(model, api_key, timeout, temperature)
    # Everything else is treated as OpenAI-compatible.
    if not base_url:
        base_url = {
            "deepseek": "https://api.deepseek.com",
            "openrouter": "https://openrouter.ai/api/v1",
            "gemma": "https://generativelanguage.googleapis.com/v1beta/openai/",
        }.get(provider, "")
    if base_url:
        # Raw httpx caller — full header control, works with self-hosted vLLM
        # (literal `EMPTY` key) as well as hosted OpenAI-compatible APIs.
        return RawHttpLLM(model, base_url, api_key or None, timeout, temperature)
    if not api_key:
        logger.warning("verifier.no_api_key provider=%s — falling back to mock", provider)
        return MockLLM()
    return OpenAICompatibleLLM(model, api_key, None, timeout, temperature)


def reset_llm_cache() -> None:
    """Used by tests when settings change at runtime."""
    global _client
    _client = None
