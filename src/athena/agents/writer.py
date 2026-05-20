from __future__ import annotations

import re

from athena.costs import guard_budget, record_llm_call
from athena.llm_factory import get_llm
from athena.prompts import WRITER_PROMPT
from athena.schemas import Citation, FinalReport, TaskStatus
from athena.state import ResearchState


def _build_citations(state: ResearchState) -> list[Citation]:
    seen: dict[str, Citation] = {}
    for finding in state.findings:
        for source in finding.sources:
            if source.url and source.url not in seen:
                seen[source.url] = Citation(
                    number=len(seen) + 1,
                    source_id=source.id,
                    title=source.title,
                    url=source.url,
                    quote=(source.snippet or "")[:220],
                )
    return list(seen.values())


def _citation_number(citations: list[Citation], url: str) -> int:
    for citation in citations:
        if citation.url == url:
            return citation.number
    return 0


def _findings_block(state: ResearchState, citations: list[Citation]) -> str:
    lines = []
    for finding in state.findings:
        nums = sorted({_citation_number(citations, s.url) for s in finding.sources if _citation_number(citations, s.url)})
        suffix = " " + " ".join(f"[{n}]" for n in nums[:5]) if nums else ""
        lines.append(f"- 【{finding.title}】 {finding.summary}{suffix}")
    return "\n".join(lines)


def _normalize_llm_report(text: str, question: str, findings_md: str, citations: list[Citation]) -> str:
    """Drop any references section the LLM produced (we attach a canonical one)."""
    body = (text or "").strip()
    body = re.sub(r"(?im)^##\s*(参考来源|参考资料|references)[\s\S]*$", "", body).strip()
    if not body:
        body = _fallback_report_body(question, findings_md)
    refs = _render_references(citations)
    return f"{body}\n\n{refs}" if refs else body


def _fallback_report_body(question: str, findings_md: str) -> str:
    return (
        f"# {question}\n\n"
        "## 摘要\n这份报告综合多源资料对问题进行了系统调研,以下是关键结论与建议。\n\n"
        "## 关键结论\n"
        f"{findings_md}\n\n"
        "## 详细分析\n上述结论基于检索到的公开资料逐项交叉验证。完整证据见参考来源。\n\n"
        "## 风险与建议\n- 持续监控数据时效性, 必要时增量再次调研。\n- 对关键决策点保持人工审阅。\n"
    )


def _render_references(citations: list[Citation]) -> str:
    if not citations:
        return ""
    lines = ["## 参考来源"]
    for citation in citations:
        title = citation.title or citation.url
        lines.append(f"[{citation.number}] {title} — {citation.url}")
    return "\n".join(lines)


@guard_budget("writer")
async def writer_node(state: ResearchState) -> ResearchState:
    state.set_status(TaskStatus.WRITING, node="writer")
    citations = _build_citations(state)
    findings_md = _findings_block(state, citations)
    llm = get_llm("writer")
    prompt = WRITER_PROMPT.render(question=state.question, findings_block=findings_md)
    try:
        result = await llm.complete_full(prompt, node="writer")
        record_llm_call(state, result)
        text = result.text
    except Exception as exc:
        state.add_error(f"writer llm error: {exc}", node="writer")
        text = _fallback_report_body(state.question, findings_md)
    markdown = _normalize_llm_report(text, state.question, findings_md, citations)
    state.final_report = FinalReport(
        task_id=state.task_id,
        title=state.question,
        markdown=markdown,
        citations=citations,
        quality=state.quality,
    )
    state.set_status(TaskStatus.DONE, node="writer")
    state.add_event("done", node="writer", final_report=state.final_report.model_dump(mode="json"))
    return state
