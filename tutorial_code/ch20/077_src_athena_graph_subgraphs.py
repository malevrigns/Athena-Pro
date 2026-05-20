"""
子图组装。每个子图是一个独立的 StateGraph,在主图里当节点用。
"""
from langgraph.graph import StateGraph, START, END

from athena.agents.fact_checker import (
    claim_extractor_node,
    claim_verifier_node,
)
from athena.agents.citation_validator import (
    citation_node,
)
from athena.state.schemas import (
    CitationCheckState,
    FactCheckState,
    ResearchState,
)


def build_fact_checker_subgraph():
    """事实核查子图。
    
    流程:
        提取 claims → 逐个验证(可并发) → 汇总 disputed
    """
    sg = StateGraph(FactCheckState)
    sg.add_node("extract_claims", claim_extractor_node)
    sg.add_node("verify_claims", claim_verifier_node)
    sg.add_edge(START, "extract_claims")
    sg.add_edge("extract_claims", "verify_claims")
    sg.add_edge("verify_claims", END)
    return sg.compile()


def build_citation_validator_subgraph():
    """引用验证子图。
    
    流程:
        检查每个 Finding 的来源 URL 真实性 / 可访问性 → 汇总 issues
    """
    sg = StateGraph(CitationCheckState)
    sg.add_node("validate", citation_node)
    sg.add_edge(START, "validate")
    sg.add_edge("validate", END)
    return sg.compile()