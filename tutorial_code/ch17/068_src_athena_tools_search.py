"""
Web 搜索工具:Tavily 主、网页直抓 fallback。

特性:
- tenacity 重试(指数退避 + jitter)
- Redis LRU 缓存(同样的 query 1 小时内复用)
- 异常时不向 LLM 暴露技术细节
"""
from __future__ import annotations
import hashlib
import json
import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from tavily import AsyncTavilyClient
from tenacity import (
    AsyncRetrying, retry_if_exception_type,
    stop_after_attempt, wait_exponential_jitter,
)

from athena.config import get_settings
from athena.tools.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

_settings = get_settings()
_tavily_client: AsyncTavilyClient | None = None


def _get_tavily() -> AsyncTavilyClient:
    """惰性初始化 Tavily 客户端。"""
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = AsyncTavilyClient(
            api_key=_settings.llm.openai_api_key.get_secret_value()
            # 实际应有独立的 TAVILY_API_KEY,这里简化
        )
    return _tavily_client


def _cache_key(query: str, max_results: int) -> str:
    raw = f"search:{query}:{max_results}"
    return "athena:" + hashlib.md5(raw.encode()).hexdigest()


async def _tavily_search(query: str, max_results: int) -> list[dict]:
    """Tavily 主搜索。失败抛异常,由外层 retry 处理。"""
    client = _get_tavily()
    result = await client.search(
        query=query,
        max_results=max_results,
        search_depth="advanced",
        include_answer=False,
    )
    return [
        {
            "url": r["url"],
            "title": r["title"],
            "snippet": r.get("content", "")[:500],
        }
        for r in result.get("results", [])
    ]


async def _ddg_fallback(query: str, max_results: int) -> list[dict]:
    """Tavily 挂掉时的降级搜索:DuckDuckGo HTML 抓取。
    
    生产中可换成 SerpAPI / Bing API / 你的自建搜索。
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Athena/1.0)"},
        )
        # 实际需要 BeautifulSoup 解析,这里简化为示意
        return [{
            "url": "https://duckduckgo.com",
            "title": f"Fallback result for: {query}",
            "snippet": resp.text[:500],
        }][:max_results]


@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """从互联网搜索信息。
    
    Args:
        query: 搜索关键词(3-8 个词最佳)
        max_results: 返回结果数,默认 5
    
    Returns:
        多条结果的格式化字符串,每条含 URL / 标题 / 摘要
    """
    cache_key = _cache_key(query, max_results)
    
    # ① 查缓存
    cached = await cache_get(cache_key)
    if cached:
        logger.info("search.cache_hit", extra={"query": query})
        return cached
    
    # ② Tavily 主路径(带 retry)
    results: list[dict] | None = None
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=1, max=8),
            retry=retry_if_exception_type((httpx.HTTPError, TimeoutError)),
            reraise=True,
        ):
            with attempt:
                results = await _tavily_search(query, max_results)
    except Exception as e:
        logger.warning(
            "search.tavily_failed_using_fallback",
            extra={"query": query, "error": str(e)},
        )
        # ③ Fallback
        try:
            results = await _ddg_fallback(query, max_results)
        except Exception as e2:
            logger.error("search.all_failed", extra={"error": str(e2)})
            return f"搜索暂时不可用,跳过此查询。详情:{type(e2).__name__}"
    
    if not results:
        return "无搜索结果。请尝试其他关键词。"
    
    # ④ 格式化 + 写缓存
    formatted = "\n---\n".join(
        f"【{r['title']}】\n{r['snippet']}\n来源: {r['url']}"
        for r in results
    )
    await cache_set(cache_key, formatted, ttl_seconds=3600)
    
    return formatted