"""
检查 findings 引用的 URL 是否真实可访问。
LLM 偶尔会幻觉一个看起来合理但实际不存在的 URL,这一步是关键的反幻觉门。
"""
from __future__ import annotations
import asyncio
import logging

import httpx

from athena.state.schemas import CitationCheckState, Finding

logger = logging.getLogger(__name__)


async def _head_check(url: str, timeout: float = 5.0) -> tuple[str, bool, str]:
    """HEAD 请求验证 URL 可访问性。"""
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Athena Validator)"},
        ) as client:
            resp = await client.head(url)
            if resp.status_code >= 400:
                return url, False, f"HTTP {resp.status_code}"
            return url, True, "OK"
    except Exception as e:
        return url, False, type(e).__name__


async def citation_node(state: CitationCheckState):
    """并发检查所有 findings 的所有 URL。"""
    findings: list[Finding] = state["findings"]
    
    # 收集所有唯一 URL
    url_to_findings: dict[str, list[str]] = {}
    for f in findings:
        for s in f.sources:
            url_to_findings.setdefault(s.url, []).append(f.topic_id)
    
    # 并发 HEAD 检查(限制并发数,避免对目标站点造成压力)
    sem = asyncio.Semaphore(10)
    
    async def check_one(url: str):
        async with sem:
            return await _head_check(url)
    
    results = await asyncio.gather(
        *(check_one(url) for url in url_to_findings.keys()),
        return_exceptions=False,
    )
    
    issues: list[str] = []
    for url, ok, reason in results:
        if not ok:
            affected = url_to_findings[url]
            issues.append(
                f"❌ 引用不可访问: {url} ({reason}),影响 findings: {','.join(affected)}"
            )
    
    logger.info(
        "citation_validator.done",
        extra={"total_urls": len(url_to_findings), "broken": len(issues)},
    )
    
    return {"issues": issues}