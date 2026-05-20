"""
FactChecker 子图的两个节点。

设计:
- claim_extractor 从所有 findings 抽出"可验证陈述"
- claim_verifier 用 LLM 判断各 claim 是否被 ≥2 来源支持
"""
from __future__ import annotations
import logging
from typing import Literal

from langchain_openai import ChatOpenAI
from langgraph.graph import END
from langgraph.types import Command
from pydantic import BaseModel, Field

from athena.config import get_settings
from athena.observability.costs import track_llm_cost
from athena.state.schemas import Claim, FactCheckState, Finding

logger = logging.getLogger(__name__)
_settings = get_settings()


# ============= 提取阶段的 schema =============

class ExtractedClaim(BaseModel):
    text: str = Field(..., description="一句陈述,含具体数字/事实")
    finding_topic_id: str
    source_urls: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    claims: list[ExtractedClaim] = Field(..., max_length=20)


# ============= 验证阶段的 schema =============

class Verdict(BaseModel):
    verified: bool = Field(..., description="True=多源印证, False=孤证/矛盾")
    confidence: float = Field(..., ge=0, le=1)
    note: str = Field(..., description="判断依据,简短一句")


# ============= 节点 1:提取 claims =============

async def claim_extractor_node(state: FactCheckState):
    """从所有 findings 里抽取可验证陈述。"""
    findings: list[Finding] = state["findings"]
    
    findings_text = "\n\n".join(
        f"【方向:{f.topic}】\n{f.summary}\n来源:{', '.join(s.url for s in f.sources)}"
        for f in findings
    )
    
    system = """你是一名严谨的事实核查员。
请从下面的研究材料中,抽取所有【可验证】的陈述。

可验证的陈述特征:
✓ 含具体数字、日期、机构、产品名
✓ 不是观点("我们认为...")
✓ 不是泛泛而谈("AI 正在发展")

每个 claim 必须关联到一个 finding_topic_id 和它来自的来源 URL(可能多个)。
"""
    
    llm = ChatOpenAI(
        model=_settings.llm.primary_model,
        temperature=0,
    ).with_structured_output(ExtractionResult)
    
    with track_llm_cost(node="fact_checker.extract", model=_settings.llm.primary_model):
        result: ExtractionResult = await llm.ainvoke([
            {"role": "system", "content": system},
            {"role": "user", "content": findings_text},
        ])
    
    claims = [
        Claim(
            text=c.text,
            finding_topic_id=c.finding_topic_id,
            source_urls=c.source_urls,
        )
        for c in result.claims
    ]
    
    logger.info("fact_checker.extracted", extra={"claims_count": len(claims)})
    return {"claims": claims}


# ============= 节点 2:批量验证 claims =============

async def claim_verifier_node(state: FactCheckState):
    """对每个 claim 判断是否被多源支持。
    
    简化实现:用 LLM 综合判断(它能看到所有 findings 和 sources)。
    生产中更严谨的做法:针对每个 claim 实际 fetch 一遍来源验证。
    """
    claims = state["claims"]
    findings = state["findings"]
    
    if not claims:
        return {"disputed": []}
    
    # 准备验证用的上下文:所有 findings 的来源 URL 与摘要
    sources_context = "\n".join(
        f"- [{f.topic_id}] {f.summary[:300]}"
        for f in findings
    )
    
    # 单个 LLM 调用判断所有 claims(批量降低成本)
    claims_text = "\n".join(f"{i+1}. {c.text}" for i, c in enumerate(claims))
    
    system = """你是事实核查员。对下面每个陈述,判断它是否被【至少两个独立来源】支持。
- 只有一个来源支持 → verified=false, note="孤证"
- 来源之间互相矛盾 → verified=false, note="冲突:..."
- 多源一致支持 → verified=true

注意:不要凭你自己的知识判断,只看提供的来源。
"""
    
    user = f"【所有来源】\n{sources_context}\n\n【待验证陈述】\n{claims_text}"
    
    class BatchVerdict(BaseModel):
        verdicts: list[Verdict]
    
    llm = ChatOpenAI(
        model=_settings.llm.primary_model,
        temperature=0,
    ).with_structured_output(BatchVerdict)
    
    with track_llm_cost(node="fact_checker.verify", model=_settings.llm.primary_model):
        batch: BatchVerdict = await llm.ainvoke([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])
    
    disputed: list[Claim] = []
    for claim, v in zip(claims, batch.verdicts):
        claim.verified = v.verified
        claim.verification_note = v.note
        if not v.verified:
            disputed.append(claim)
    
    logger.info(
        "fact_checker.verified",
        extra={"total": len(claims), "disputed": len(disputed)},
    )
    
    return {"disputed": disputed}