from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

from pydantic import BaseModel

from athena.config import get_settings
from athena.observability import logger
from athena.schemas import Source
from athena.tools.retry import async_retry


ALLOWED_RESULT_SCHEMES = {"http", "https"}


def _validate_web_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_RESULT_SCHEMES or not parsed.netloc:
        raise ValueError("search result url must be an absolute http(s) URL")
    return url


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    score: float = 0.7

    def to_source(self) -> Source:
        _validate_web_url(self.url)
        is_mock = self.url.startswith("https://example.com/")
        return Source(
            title=self.title,
            url=self.url,
            snippet=self.snippet,
            credibility=self.score,
            source_type="mock" if is_mock else "web",
        )


class SearchProvider(Protocol):
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]: ...


@dataclass
class MockSearchProvider:
    """Deterministic provider for first-boot / offline demos."""
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        await asyncio.sleep(0.02)
        digest = hashlib.sha1(query.encode()).hexdigest()
        results: list[SearchResult] = []
        for idx in range(max_results):
            score = max(0.35, 0.9 - idx * 0.08)
            results.append(SearchResult(
                title=f"{query} · reference {idx + 1}",
                url=f"https://example.com/research/{digest[:8]}/{idx + 1}",
                snippet=f"Mock source about {query}. It covers market context, implementation details and risks.",
                score=score,
            ))
        return results


@dataclass
class DuckDuckGoSearchProvider:
    """Zero-config provider backed by the public DuckDuckGo HTML search.

    Uses the `ddgs` package which scrapes the public results page; no API key
    required. Suitable for development and lightweight production where the
    Tavily allowance is exhausted or unavailable.
    """

    region: str = "wt-wt"
    safesearch: str = "moderate"

    @async_retry(attempts=2, base_delay=0.3, max_delay=2.0)
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            from ddgs import DDGS  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Install `ddgs` to use DuckDuckGoSearchProvider") from exc

        def _do() -> list[dict]:
            # Strip ambient SOCKS/HTTP proxies so ddgs talks directly to the
            # public endpoint. Restored after the call to keep other modules
            # (e.g. LLM clients that may legitimately need a proxy) unaffected.
            import os
            saved: dict[str, str] = {}
            for k in ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
                if k in os.environ:
                    saved[k] = os.environ.pop(k)
            try:
                with DDGS() as ddg:
                    return list(ddg.text(query, region=self.region, safesearch=self.safesearch, max_results=max_results))
            finally:
                for k, v in saved.items():
                    os.environ[k] = v

        try:
            rows = await asyncio.to_thread(_do)
        except Exception as exc:
            logger.warning("search.duckduckgo_error query=%s err=%s", query, exc)
            raise
        out: list[SearchResult] = []
        for item in rows[:max_results]:
            url = item.get("href") or item.get("link") or ""
            if not url:
                continue
            out.append(SearchResult(
                title=item.get("title") or "Untitled",
                url=url,
                snippet=(item.get("body") or item.get("snippet") or "")[:600],
                score=0.7,
            ))
        return out


@dataclass
class TavilySearchProvider:
    api_key: str

    @async_retry(attempts=3, base_delay=0.4, max_delay=4.0)
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            from tavily import AsyncTavilyClient  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Install tavily-python to use TavilySearchProvider") from exc
        client = AsyncTavilyClient(api_key=self.api_key)
        try:
            raw = await client.search(query=query, max_results=max_results, search_depth="advanced", include_answer=False)
        except Exception as exc:
            logger.warning("search.tavily_error query=%s err=%s", query, exc)
            raise
        results: list[SearchResult] = []
        for item in raw.get("results", []):
            url = item.get("url") or ""
            if not url:
                continue
            results.append(SearchResult(
                title=item.get("title", "Untitled") or "Untitled",
                url=url,
                snippet=(item.get("content") or "")[:600],
                score=float(item.get("score", 0.7) or 0.7),
            ))
        return results


@dataclass
class _CacheEntry:
    expires_at: float
    results: list[SearchResult]


@dataclass
class CachedSearchProvider:
    inner: SearchProvider
    ttl_sec: int = 1800
    cache: dict[str, _CacheEntry] = field(default_factory=dict)

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        key = f"{query.strip().lower()}::{max_results}"
        now = time.time()
        entry = self.cache.get(key)
        if entry and entry.expires_at > now:
            return entry.results
        try:
            results = await self.inner.search(query, max_results=max_results)
        except Exception:
            if entry:  # serve stale
                logger.warning("search.fallback_to_stale_cache key=%s", key)
                return entry.results
            raise
        self.cache[key] = _CacheEntry(expires_at=now + self.ttl_sec, results=results)
        return results


_provider: SearchProvider | None = None


def get_search_provider() -> SearchProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        if settings.search_provider == "tavily" and settings.tavily_api_key:
            inner: SearchProvider = TavilySearchProvider(settings.tavily_api_key)
        elif settings.search_provider == "duckduckgo":
            inner = DuckDuckGoSearchProvider()
        else:
            inner = MockSearchProvider()
        _provider = CachedSearchProvider(inner, ttl_sec=settings.search_cache_ttl_sec)
    return _provider


def reset_search_cache() -> None:
    global _provider
    _provider = None


class SearchClient:
    def __init__(self, provider: SearchProvider | None = None):
        self.provider = provider or get_search_provider()

    async def web_search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return await self.provider.search(query, max_results=max_results)
