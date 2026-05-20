"""
Writer Agent:整合所有 findings,产出带引用的最终报告。

引用机制:
- 所有 sources 集中编号 [1] [2] [3] ...
- Prompt 强制 Writer 在每个论断后写 [n]
- 报告末尾自动追加 "## 来源" section
- 同时输出 report_metadata 给 API 使用
"""
from __future__ import annotations
import logging
from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END
from langgraph.types import Command

from athena.config import get_settings
from athena.observability.costs import track_llm_cost
from athena.state.schemas import Phase, ResearchState

logger = logging.getLogger(__name__)
_settings = get_settings()


def _build_citation_table(state: ResearchState) -> tuple[str, dict]:
    """把所有 findings 的 sources 编号,构建引用表。
    
    返回:
        - context_text: 给 Writer 看的"编号化"findings 文本
        - cite_map: {编号: Source} 用于最后渲染来源列表
    """
    cite_map: dict[int, dict] = {}  # {1: {"url": ..., "title": ...}}
    url_to_id: dict[str, int] = {}
    next_id = 1
    
    blocks: list[str] = []
    for f in state.get("findings", []):
        # 给这个 finding 的每个 source 分配编号
        cite_ids: list[int] = []
        for s in f.sources:
            if s.url not in url_to_id:
                url_to_id[s.url] = next_id
                cite_map[next_id] = {"url": s.url, "title": s.title or s.url}
                next_id += 1
            cite_ids.append(url_to_id[s.url])
        
        cite_tags = "".join(f"[{i}]" for i in cite_ids)
        blocks.append(
            f"### 方向:{f.topic}\n"
            f"{f.summary} {cite_tags}\n"
            f"可用引用编号:{cite_ids}"
        )
    
    return "\n\n".join(blocks), cite_map


def _render_sources_section(cite_map: dict) -> str:
    """渲染最终报告底部的 ## 来源 section。"""
    if not cite_map:
        return ""
    lines = ["\n\n## 来源\n"]
    for cid in sorted(cite_map):
        info = cite_map[cid]
        lines.append(f"[{cid}] [{info['title']}]({info['url']})")
    return "\n".join(lines)


WRITER_PROMPT = """你是一名资深科技撰稿人,正在为企业研究情报平台 Athena 撰写报告。

【用户原问题】
{question}

【研究材料】(每条材料已标好可用的引用编号 [n])

{context_text}

【已识别的争议陈述,务必谨慎处理或排除】
{disputed_text}

【写作要求】
1. 标题用 `# {question}` 作为一级标题
2. 第一段是 `## 概述`,简要 80-120 字回答原问题
3. 每个主要研究方向用 `## 二级标题`
4. **关键要求:每一个具体论断/数据后面,必须跟一个 `[n]` 引用编号**
5. 引用编号必须来自给定的"可用引用编号"列表,不要瞎编
6. 最后用 `## 关键洞察`,提炼 3 条核心结论
7. 全文 800-1500 字
8. 不要写"我"或"研究员",要客观第三人称

【禁止】
✗ 在文中提到争议陈述
✗ 引用未在可用编号列表里的 [n]
✗ 编造数据或来源
✗ 加 ```markdown``` 包装符

直接输出 Markdown 正文。"""


async def writer_node(
    state: ResearchState,
) -> Command[Literal["__end__"]]:
    settings = get_settings()
    
    # 1. 编号化所有 sources
    context_text, cite_map = _build_citation_table(state)
    
    # 2. 准备争议陈述列表(让 Writer 避开)
    disputed = state.get("disputed_claims", [])
    disputed_text = "\n".join(
        f"  • {c.text[:100]} ({c.verification_note})"
        for c in disputed[:8]
    ) or "  (无)"
    
    prompt = WRITER_PROMPT.format(
        question=state["question"],
        context_text=context_text,
        disputed_text=disputed_text,
    )
    
    # 3. 调用 LLM(温度稍高,允许文笔活跃)
    llm = ChatOpenAI(
        model=settings.llm.primary_model,
        temperature=0.3,
        max_tokens=4096,
    )
    
    with track_llm_cost(node="writer", model=settings.llm.primary_model) as tracker:
        response = await llm.ainvoke([
            {"role": "system", "content": prompt},
        ])
    
    report_body = response.content
    
    # 4. 追加来源 section
    report = report_body + _render_sources_section(cite_map)
    
    # 5. 计算元数据(给 API / 监控用)
    citation_count = report_body.count("[")  # 粗略计数
    word_count = len(report_body)
    
    metadata = {
        "word_count": word_count,
        "citation_count": citation_count,
        "sources_count": len(cite_map),
        "disputed_skipped": len(disputed),
    }
    
    logger.info("writer.done", extra=metadata)
    
    msg = HumanMessage(
        content=f"📝 报告完成 · {word_count} 字 · {citation_count} 处引用 · ¥{tracker.cost_cny:.4f}",
        name="writer",
    )
    
    return Command(
        goto=END,
        update={
            "phase": Phase.COMPLETED,
            "final_report": report,
            "report_metadata": metadata,
            "messages": [msg],
            "total_tokens": tracker.tokens,
            "total_cost_cny": tracker.cost_cny,
        },
    )