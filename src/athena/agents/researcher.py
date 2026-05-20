from __future__ import annotations

import asyncio
from dataclasses import dataclass

from athena.config import get_settings
from athena.costs import guard_budget, record_llm_call
from athena.llm_factory import get_llm
from athena.prompts import RESEARCHER_PROMPT
from athena.schemas import Finding, ResearchTopic, Source, TaskStatus
from athena.state import ResearchState
from athena.tools.knowledge import retrieve_knowledge_sources
from athena.tools.search import SearchClient


def _format_sources_for_prompt(sources: list[Source]) -> str:
    if not sources:
        return "(无来源, 直接基于常识回答)"
    lines = []
    for idx, s in enumerate(sources, 1):
        snippet = (s.snippet or "").replace("\n", " ")[:280]
        lines.append(f"[{idx}] {s.title} — {s.url}\n    {snippet}")
    return "\n".join(lines)


@dataclass
class Researcher:
    search: SearchClient

    async def run_topic(self, topic: ResearchTopic, state: ResearchState | None = None) -> Finding:
        settings = get_settings()
        llm = get_llm("researcher")
        sources: list[Source] = []
        sources.extend(await retrieve_knowledge_sources(topic, limit=settings.search_max_results))
        queries = topic.search_queries or [topic.question]
        for query in queries[:3]:
            try:
                results = await self.search.web_search(query, max_results=settings.search_max_results)
            except Exception:
                results = []
            for result in results:
                src = result.to_source()
                if any(existing.url == src.url for existing in sources):
                    continue
                sources.append(src)
        # cap sources to avoid prompt bloat
        top_sources = sources[: max(4, settings.search_max_results)]
        prompt = RESEARCHER_PROMPT.render(
            title=topic.title,
            question=topic.question,
            source_count=len(top_sources),
            sources_block=_format_sources_for_prompt(top_sources),
        )
        try:
            model_result = await llm.complete_full(prompt, node="researcher")
            if state is not None:
                record_llm_call(state, model_result)
            summary = model_result.text.strip()
        except Exception as exc:
            summary = f"(LLM 调用失败, 退回到结构化摘要)\n{exc}"
        if not summary:
            summary = f"基于 {len(top_sources)} 个来源对「{topic.title}」做了交叉对比。"
        evidence = [f"{src.title}: {src.snippet[:200]}" for src in top_sources[:4]]
        confidence = min(0.95, 0.55 + 0.08 * len({s.url for s in top_sources}))
        return Finding(
            topic_id=topic.id,
            title=topic.title,
            summary=summary,
            evidence=evidence,
            sources=top_sources,
            confidence=round(confidence, 3),
        )


async def _run_topics(state: ResearchState, topics: list[ResearchTopic]) -> list[Finding]:
    settings = get_settings()
    researcher = Researcher(SearchClient())
    semaphore = asyncio.Semaphore(settings.max_parallel_researchers)

    async def _wrapped(topic: ResearchTopic) -> Finding:
        async with semaphore:
            return await researcher.run_topic(topic, state=state)

    return list(await asyncio.gather(*[_wrapped(t) for t in topics]))


@guard_budget("researcher")
async def researcher_node(state: ResearchState) -> ResearchState:
    if not state.plan:
        raise ValueError("researcher_node requires a plan")
    state.set_status(TaskStatus.RESEARCHING, node="researcher")
    existing_topic_ids = {f.topic_id for f in state.findings}
    pending_topics = [t for t in state.plan.topics if t.id not in existing_topic_ids]
    if not pending_topics:
        return state
    findings = await _run_topics(state, pending_topics)
    for finding in findings:
        state.add_finding(finding)
    return state
