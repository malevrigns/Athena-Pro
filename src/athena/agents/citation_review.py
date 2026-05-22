"""Citation review — the final pipeline step before a task is marked done.

Two modes, selected by the server-global `CitationSettings`:

* manual  — emit a `citation_review` event so the UI can prompt the user to
            verify each citation by hand. Nothing is decided automatically.
* auto    — an independently-configured second model judges every citation
            (pass / flag / reject) and the decisions are persisted, so the
            citation page is already filled in when the user looks.

The terminal `done` event is emitted here (not by the writer) so the citation
review always reaches the SSE client before the stream closes.
"""

from __future__ import annotations

import json
import re

from athena.app_settings import CitationSettings, load_citation_settings
from athena.costs import TokenLedger
from athena.llm_factory import build_verifier_llm
from athena.observability import logger
from athena.persistence import get_store
from athena.schemas import Citation, TaskStatus
from athena.state import ResearchState

_VERDICTS = {"pass", "flag", "reject"}

_PROMPT = """研究问题:{question}

待核对引用:
- 编号:[{number}]
- 来源标题:{title}
- 来源链接:{url}
- 摘录片段:{quote}

请判断这条引用能否作为该研究问题报告的可靠依据,并只返回一个 JSON 对象:
{{"verdict": "pass|flag|reject", "reason": "一句话中文理由"}}
判定标准:
- pass:来源可靠、与问题相关、摘录有实质内容
- flag:存在疑点(时效性 / 相关性 / 权威性不足),建议人工复核
- reject:来源无效、不相关或无法支撑结论"""


def _heuristic(c: Citation) -> tuple[str, str]:
    """Deterministic fallback verdict when no usable model output is available."""
    url = (c.url or "").strip().lower()
    if not (url.startswith("http://") or url.startswith("https://")):
        return "reject", "无有效来源链接"
    if "example.com" in url:
        return "flag", "示例占位链接,建议人工核对"
    return "pass", "链接有效(启发式判定)"


def _parse_verdict(text: str) -> tuple[str, str] | None:
    """Extract the first {"verdict": ..., "reason": ...} object from model text."""
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except Exception:
        return None
    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in _VERDICTS:
        return None
    reason = str(data.get("reason", "")).strip() or "模型未给出理由"
    return verdict, reason


async def _auto_verify(
    state: ResearchState,
    citations: list[Citation],
    settings: CitationSettings,
) -> dict:
    """Let the second model decide every citation; persist + tally the verdicts."""
    verifier = settings.verifier
    llm = build_verifier_llm(verifier.provider, verifier.model, verifier.api_key, verifier.base_url)
    store = get_store()
    counts = {"pass": 0, "flag": 0, "reject": 0}
    total_in = total_out = 0
    model_name = verifier.model or "heuristic"

    for c in citations:
        verdict, reason = _heuristic(c)
        try:
            prompt = _PROMPT.format(
                question=state.question,
                number=c.number,
                title=c.title or "(无标题)",
                url=c.url or "(无链接)",
                quote=(c.quote or "(无摘录)")[:500],
            )
            res = await llm.complete_full(prompt, node="citation_review")
            total_in += getattr(res, "input_tokens", 0) or 0
            total_out += getattr(res, "output_tokens", 0) or 0
            if getattr(res, "model", ""):
                model_name = res.model
            parsed = _parse_verdict(res.text)
            if parsed:
                verdict, reason = parsed
        except Exception as exc:  # noqa: BLE001
            logger.warning("citation_review.verify_failed n=%s err=%s", c.number, exc)
        counts[verdict] = counts.get(verdict, 0) + 1
        try:
            await store.upsert_citation_verification(
                state.task_id, c.number, verdict, reason, decided_by="model",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("citation_review.persist_failed n=%s err=%s", c.number, exc)

    if total_in or total_out:
        ledger: TokenLedger = state.metadata.setdefault("ledger", TokenLedger())
        state.add_usage(ledger.add(model_name, "citation_review", total_in, total_out))

    return {"mode": "auto", "total": len(citations), "model": model_name, **counts}


async def citation_review_node(state: ResearchState) -> ResearchState:
    """Verify the report's citations, then emit the terminal `done` event."""
    citations = list(state.final_report.citations) if state.final_report else []
    total = len(citations)

    # Idempotent: a resumed run keeps the citation review it already did.
    if not state.metadata.get("citation_review"):
        try:
            settings = await load_citation_settings()
        except Exception as exc:  # noqa: BLE001
            logger.warning("citation_review.settings_load_failed err=%s", exc)
            settings = CitationSettings()

        if total == 0:
            state.metadata["citation_review"] = {"mode": "empty", "total": 0}
        elif settings.manual_review:
            state.metadata["citation_review"] = {"mode": "manual", "total": total}
            state.add_event(
                "citation_review", node="citation_review",
                mode="manual", total=total, pending=total,
                message=f"报告生成了 {total} 条引用,等待人工核对",
            )
        else:
            try:
                result = await _auto_verify(state, citations, settings)
            except Exception as exc:  # noqa: BLE001
                logger.warning("citation_review.auto_failed err=%s", exc)
                result = {"mode": "auto", "total": total, "model": "", "pass": 0, "flag": 0, "reject": 0}
            state.metadata["citation_review"] = result
            state.add_event("citation_review", node="citation_review", **result)

    state.set_status(TaskStatus.DONE, node="citation_review")
    state.add_event(
        "done", node="citation_review",
        final_report=state.final_report.model_dump(mode="json") if state.final_report else {},
    )
    return state
