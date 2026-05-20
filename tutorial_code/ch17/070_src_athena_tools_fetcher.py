"""
抓取指定 URL 的正文内容。
研究员引用某条搜索结果后,可用此工具拉取完整内容。
"""
from __future__ import annotations
import logging
import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def fetch_url(url: str, max_chars: int = 4000) -> str:
    """抓取指定 URL 的正文。
    
    Args:
        url: 必须以 http(s):// 开头
        max_chars: 最大返回字符数,防止上下文爆炸
    """
    if not url.startswith(("http://", "https://")):
        return "错误:url 必须以 http:// 或 https:// 开头"
    
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Athena Research Bot)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("fetch.failed", extra={"url": url, "error": str(e)})
        return f"无法抓取该 URL: {type(e).__name__}"
    
    # 用 BeautifulSoup 抽正文
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[内容已截断]"
    
    return text


# 导出给 Researcher 用的工具集
RESEARCH_TOOLS = [
    # 第一个是搜索,通过 from athena.tools.search 引入
    # 第二个是抓取
]