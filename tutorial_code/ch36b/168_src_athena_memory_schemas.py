"""长期记忆数据模型"""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
from uuid import uuid4


# ============ 用户反馈(原始信号)============
class Feedback(BaseModel):
    """用户对一次任务结果的反馈,raw signal"""
    feedback_id: str = Field(default_factory=lambda: f"fb_{uuid4().hex[:12]}")
    task_id: str
    user_id: str | None = None
    
    # 反馈本体
    rating: Literal["up", "down"]
    comment: str = ""                 # 用户文字说明,可能为空
    
    # 上下文(用于后续抽取)
    question: str                      # 原始问题
    final_report: str                  # 报告全文(用于让 LLM 看哪里有问题)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============ 抽取后的 Anti-Pattern(可注入)============
class AntiPattern(BaseModel):
    """从反馈中抽象出的'教训',跨任务可复用"""
    pattern_id: str = Field(default_factory=lambda: f"ap_{uuid4().hex[:12]}")
    
    # 触发条件(LLM 抽取)
    trigger_summary: str               # "调研 AI / 软件框架类话题时"
    trigger_keywords: list[str]        # ["AI", "framework", "对比", ...]
    
    # 教训本体
    failure_mode: str                  # "倾向引用 2 年以上的过时来源"
    correction: str                    # "确保至少 50% 来源是 6 个月内,优先官方文档"
    severity: Literal["low", "medium", "high"] = "medium"
    
    # 溯源 / 衰减
    source_feedback_ids: list[str] = Field(default_factory=list)  # 哪些反馈产生的
    hit_count: int = 0                # 被注入过几次
    last_hit_at: datetime | None = None
    
    # 自动衰减字段
    confidence: float = 1.0           # 0-1,根据 hit 后的反馈调整
    is_active: bool = True
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============ 检索结果(注入到 prompt 用)============
class MemoryHit(BaseModel):
    """向量检索返回的记忆项,带相似度分数"""
    pattern: AntiPattern
    similarity: float                  # 0-1


class MemoryQuery(BaseModel):
    """查询请求(给 injector 用)"""
    question: str
    top_k: int = 3
    min_similarity: float = 0.65       # 低于此阈值视为不相关