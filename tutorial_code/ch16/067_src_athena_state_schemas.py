"""
Athena 主图与子图的 State 定义。

设计原则:
- 累积型字段(findings、disputed_claims)用 reducer
- 当前状态字段(current_topic、phase)用覆盖
- 配置/上下文走 Context schema,不进 checkpoint
"""
from __future__ import annotations
import operator
from enum import Enum
from typing import Annotated, TypedDict

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


# ============= 业务对象(Pydantic,跨节点传递)=============

class Phase(str, Enum):
    """研究流程阶段。便于 API 把进度展示给前端。"""
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    RESEARCHING = "researching"
    FACT_CHECKING = "fact_checking"
    CITATION_VALIDATING = "citation_validating"
    REVIEWING = "reviewing"
    WRITING = "writing"
    COMPLETED = "completed"
    FAILED = "failed"


class Source(BaseModel):
    """一条信息来源。"""
    url: str
    title: str
    snippet: str = ""
    fetched_at: str = ""           # ISO 时间


class Finding(BaseModel):
    """单个子主题的研究结果。"""
    topic_id: str                  # 对应 research_plan 里的 ID
    topic: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    tokens_used: int = 0
    cost_cny: float = 0.0


class Claim(BaseModel):
    """从 finding 里提取出的可验证陈述。FactChecker 子图用。"""
    text: str
    finding_topic_id: str
    source_urls: list[str] = Field(default_factory=list)
    verified: bool | None = None   # None=未核 / True=已印证 / False=矛盾
    verification_note: str = ""


# ============= 主图 State =============

class ResearchState(MessagesState):
    """整个研究任务的共享状态。
    
    继承 MessagesState 自动获得带 add_messages reducer 的 messages 字段。
    """
    # —— 输入 ——
    task_id: str                                    # 任务唯一 ID
    question: str                                   # 用户原始问题
    
    # —— Planner 产出 ——
    research_plan: list[dict]                       # [{id, topic, why}, ...]
    plan_revision: int                              # 第几版 plan
    
    # —— 流程跟踪 ——
    phase: Phase                                    # 当前阶段
    current_topic_ids: list[str]                    # 本轮要并行研究的 topic ids
    
    # —— Researcher 累积 ——
    findings: Annotated[list[Finding], operator.add]
    
    # —— 质量门控产出 ——
    disputed_claims: Annotated[list[Claim], operator.add]
    citation_issues: Annotated[list[str], operator.add]
    review_feedback: str
    revision_count: int
    
    # —— Writer 产出 ——
    final_report: str
    report_metadata: dict                           # {word_count, citation_count, ...}
    
    # —— 成本/可观测性 ——
    total_tokens: Annotated[int, operator.add]
    total_cost_cny: Annotated[float, operator.add]
    error_log: Annotated[list[str], operator.add]


# ============= 子图 State =============

class FactCheckState(TypedDict):
    """FactChecker 子图的局部 state。"""
    findings: list[Finding]                         # 输入
    claims: list[Claim]                             # 提取出的陈述
    disputed: Annotated[list[Claim], operator.add]  # 有矛盾的


class CitationCheckState(TypedDict):
    """CitationValidator 子图的局部 state。"""
    findings: list[Finding]
    issues: Annotated[list[str], operator.add]


# ============= Context Schema(LangGraph 1.1 新机制)=============
# 不进 checkpoint,但在节点里可访问

class RuntimeContext(BaseModel):
    """运行时上下文,跨节点共享但不持久化。
    
    通过 graph.invoke(..., context=RuntimeContext(...)) 传入,
    节点签名变成 (state, runtime: Runtime[RuntimeContext])。
    """
    user_id: str
    request_id: str
    cost_budget_cny: float = 1.0
    cost_warning_threshold_cny: float = 0.5
    enable_hitl: bool = True
    hitl_timeout_seconds: int = 1800
    parallel_researchers: int = 5
    
    # 模型选择,允许在运行时切换
    primary_model: str = "gpt-4o-mini"
    fallback_model: str = "claude-3-5-haiku-latest"