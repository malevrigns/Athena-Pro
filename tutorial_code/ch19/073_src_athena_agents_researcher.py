"""
Researcher Agent:对单个子主题深度调研。

设计:外层是图节点(组装、归档),内层是 create_react_agent ReAct 循环。
每个 Researcher 实例独立处理一个 topic_id,通过 Send API 并行启动。
"""
from __future__ import annotations
import logging
import time
from typing import Literal, TypedDict

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command

from athena.config import get_settings
from athena.observability.costs import track_llm_cost
from athena.prompts.researcher import RESEARCHER_PROMPT
from athena.state.schemas import Finding, Phase, ResearchState, Source
from athena.tools.fetcher import fetch_url
from athena.tools.search import web_search

logger = logging.getLogger(__name__)
_settings = get_settings()


# ============= Send 时传递的局部 state =============

class ResearcherInput(TypedDict):
    """通过 Send 发给单个 Researcher 实例的输入。"""
    topic_id: str
    topic: str
    why: str
    task_id: str   # 用于 logging / tracing


# ============= 内层 ReAct Agent(每次调用前创建,确保 prompt 最新)=============

def _build_inner_agent():
    """构建 create_react_agent。"""
    llm = ChatOpenAI(
        model=_settings.llm.primary_model,
        temperature=0.0,        # 研究员要严谨
        timeout=_settings.llm.request_timeout,
    )
    return create_react_agent(
        model=llm,
        tools=[web_search, fetch_url],
        prompt=RESEARCHER_PROMPT,
        name="researcher_inner",
    )


_inner_agent = None

def get_inner_agent():
    global _inner_agent
    if _inner_agent is None:
        _inner_agent = _build_inner_agent()
    return _inner_agent


# ============= 外层节点 =============

async def researcher_node(
    state: ResearcherInput,
) -> Command[Literal["supervisor"]]:
    """单个子主题的研究。注意:state 类型是 ResearcherInput 不是 ResearchState!
    
    Send 机制下,这个节点接收的是 Send 传递的局部 state,
    而不是主图的完整 ResearchState。
    """
    topic_id = state["topic_id"]
    topic = state["topic"]
    task_id = state["task_id"]
    start = time.perf_counter()
    
    logger.info(
        "researcher.start",
        extra={"task_id": task_id, "topic_id": topic_id, "topic": topic},
    )
    
    # 准备给内层 agent 的输入
    user_msg = (
        f"请深度调研以下子方向,并产出一份 100-200 字的研究小结。\n\n"
        f"【子方向】{topic}\n"
        f"【为何要研究】{state['why']}\n\n"
        f"要求:\n"
        f"1. 至少调用 1-2 次 web_search 获取信息\n"
        f"2. 必要时用 fetch_url 获取关键页面的详细内容\n"
        f"3. 总结要客观、具体,包含数字和来源\n"
        f"4. 不要写'我搜索了...'之类的过程描述"
    )
    
    inner_agent = get_inner_agent()
    
    # 跑 ReAct 循环,带成本追踪
    with track_llm_cost(node="researcher", model=_settings.llm.primary_model) as tracker:
        try:
            result = await inner_agent.ainvoke(
                {"messages": [HumanMessage(content=user_msg)]},
                config={"recursion_limit": 12},  # 防止单 researcher 跑飞
            )
        except Exception as e:
            logger.exception("researcher.failed", extra={"topic_id": topic_id})
            # 失败时返回占位 finding,让流程继续
            return Command(
                goto="supervisor",
                update={
                    "findings": [Finding(
                        topic_id=topic_id,
                        topic=topic,
                        summary=f"[研究失败:{type(e).__name__}]",
                        sources=[],
                        tokens_used=tracker.tokens,
                        cost_cny=tracker.cost_cny,
                    )],
                    "error_log": [f"researcher[{topic_id}]: {e}"],
                }
            )
    
    # 提取最终结论
    summary = result["messages"][-1].content
    
    # 提取来源(从 ToolMessage 里抠 URL)
    sources = _extract_sources(result["messages"])
    
    elapsed = time.perf_counter() - start
    logger.info(
        "researcher.done",
        extra={
            "task_id": task_id, "topic_id": topic_id,
            "elapsed_s": round(elapsed, 2),
            "sources_count": len(sources),
            "cost_cny": tracker.cost_cny,
        },
    )
    
    # 包装成 Finding,通过 reducer 累加到主图 findings 字段
    finding = Finding(
        topic_id=topic_id,
        topic=topic,
        summary=summary,
        key_points=_extract_bullets(summary),
        sources=sources,
        tokens_used=tracker.tokens,
        cost_cny=tracker.cost_cny,
    )
    
    # 给主对话流加一条简报
    report_msg = HumanMessage(
        content=f"✓ 完成研究【{topic}】({len(sources)} 个来源, ¥{tracker.cost_cny:.4f})",
        name=f"researcher_{topic_id}",
    )
    
    return Command(
        goto="supervisor",
        update={
            "findings": [finding],
            "messages": [report_msg],
            "total_tokens": tracker.tokens,
            "total_cost_cny": tracker.cost_cny,
        },
    )


# ============= 辅助函数 =============

def _extract_sources(messages: list) -> list[Source]:
    """从 ToolMessage 里提取所有 URL 作为 Source。"""
    sources: list[Source] = []
    seen_urls: set[str] = set()
    
    for msg in messages:
        if msg.__class__.__name__ != "ToolMessage":
            continue
        content = msg.content if isinstance(msg.content, str) else ""
        for line in content.split("\n"):
            if "来源:" in line or "来源: " in line:
                # 简单提取,生产中可用正则更严谨
                url = line.split("来源:")[-1].strip()
                if url.startswith("http") and url not in seen_urls:
                    seen_urls.add(url)
                    sources.append(Source(url=url, title=url, snippet=""))
    
    return sources


def _extract_bullets(summary: str) -> list[str]:
    """从 summary 里抽 1-3 个 key points(简单实现)。"""
    bullets = [
        line.strip().lstrip("•-*").strip()
        for line in summary.split("\n")
        if line.strip().startswith(("•", "-", "*"))
    ]
    return bullets[:5]