from __future__ import annotations

import re
from urllib.parse import quote

from athena.persistence import get_store
from athena.schemas import ResearchTopic, Source

MAX_KNOWLEDGE_QUERIES = 8
MIN_TOKEN_LENGTH = 2


async def retrieve_knowledge_sources(topic: ResearchTopic, limit: int = 4) -> list[Source]:
    store = get_store()
    sources: list[Source] = []
    seen_item_ids: set[str] = set()
    for query in _knowledge_queries(topic):
        items, _ = await store.list_knowledge_items(search=query, limit=limit, offset=0)
        for item in items:
            item_id = str(item["id"])
            if item_id in seen_item_ids:
                continue
            seen_item_ids.add(item_id)
            sources.append(_item_to_source(item))
            if len(sources) >= limit:
                return sources
    return sources


def _knowledge_queries(topic: ResearchTopic) -> list[str]:
    raw = [*topic.search_queries, topic.title, topic.question]
    queries: list[str] = []
    for value in raw:
        _append_unique(queries, value.strip())
        for token in re.findall(r"[\w\u4e00-\u9fff]+", value):
            if len(token) >= MIN_TOKEN_LENGTH:
                _append_unique(queries, token)
        if len(queries) >= MAX_KNOWLEDGE_QUERIES:
            break
    return queries[:MAX_KNOWLEDGE_QUERIES]


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _item_to_source(item: dict) -> Source:
    summary = str(item.get("summary") or "")
    status = str(item.get("status") or "pending")
    return Source(
        id=f"kn_{item['id']}",
        title=str(item["name"]),
        url=_source_url(item),
        snippet=summary,
        credibility=0.9 if status == "verified" else 0.7,
        source_type="internal",
    )


def _source_url(item: dict) -> str:
    raw = str(item.get("source") or "")
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"/knowledge?item={quote(str(item['id']))}"
