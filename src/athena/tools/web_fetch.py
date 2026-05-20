from __future__ import annotations

import re
from dataclasses import dataclass

import httpx


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    status_code: int


def _strip_html(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


async def fetch_url(url: str, timeout: float = 8.0) -> FetchedPage:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url)
    title_match = re.search(r"<title>(.*?)</title>", response.text, flags=re.I | re.S)
    title = title_match.group(1).strip() if title_match else url
    return FetchedPage(url=str(response.url), title=title, text=_strip_html(response.text)[:8000], status_code=response.status_code)
