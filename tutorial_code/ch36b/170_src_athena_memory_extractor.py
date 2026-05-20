"""把单次反馈抽取成 anti-pattern"""
from __future__ import annotations
import json
import structlog
from langchain_openai import ChatOpenAI
from athena.memory.schemas import AntiPattern, Feedback
from athena.memory.store import get_feedback, save_anti_pattern

logger = structlog.get_logger()


EXTRACTION_PROMPT = """你是 Athena 系统的"教训分析师"。
用户对一次研究报告给了 thumbs-down,你的任务是抽象出可复用的教训,
让 Athena 在未来类似任务上避免同样错误。

## 用户反馈
原始问题: {question}
用户评论: {comment}
报告内容(节选): {report_snippet}

## 任务

分析此次失败,产出一个 JSON 对象,字段如下:

{{
  "trigger_summary": "<一句话描述什么类型的任务该警惕,如:'调研技术框架对比类问题'>",
  "trigger_keywords": ["3-6 个关键词,用于后续相似性检索"],
  "failure_mode": "<具体错在哪,如:'倾向引用 2 年以上的过时文章'>",
  "correction": "<针对性的、可执行的改进指令,如:'确保至少 50% 来源是 6 个月内的'>",
  "severity": "low|medium|high"
}}

## 重要原则

1. **抽象但不空洞**:不要写"答得不好",写"具体某种倾向"
2. **可执行**:correction 必须是 prompt 里能直接用的指令
3. **保守 severity**:除非真的严重(用户极度不满 / 涉及安全),用 medium
4. **关键词宽泛点**:让相似问题能匹配上,但不要全宇宙关键词

只输出 JSON,不要其他文字。"""


_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)


async def extract_anti_pattern(feedback: Feedback) -> AntiPattern | None:
    """从一条 feedback 抽取 anti-pattern。失败返回 None。"""
    if feedback.rating != "down":
        return None
    
    if not feedback.comment.strip() and not feedback.final_report.strip():
        # 评论为空 + 报告也空,无信息可抽
        return None
    
    # 截断报告防 context 爆
    report_snippet = feedback.final_report[:3000]
    if len(feedback.final_report) > 3000:
        report_snippet += "...(报告过长,已截断)"
    
    prompt = EXTRACTION_PROMPT.format(
        question=feedback.question,
        comment=feedback.comment or "(用户未留评论)",
        report_snippet=report_snippet,
    )
    
    response = await _llm.ainvoke(prompt)
    content = response.content.strip()
    
    # 解析 JSON · 容错
    try:
        # LLM 可能用 ```json ``` 包裹
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json\n"):
                content = content[5:]
        data = json.loads(content)
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning("extract_json_parse_failed",
                       feedback_id=feedback.feedback_id,
                       raw=content[:200])
        return None
    
    return AntiPattern(
        trigger_summary=data["trigger_summary"],
        trigger_keywords=data["trigger_keywords"],
        failure_mode=data["failure_mode"],
        correction=data["correction"],
        severity=data.get("severity", "medium"),
        source_feedback_ids=[feedback.feedback_id],
    )


async def schedule_extraction(feedback_id: str) -> None:
    """收到反馈后被 collector 后台调用"""
    feedback = await get_feedback(feedback_id)
    if feedback is None:
        return
    
    pattern = await extract_anti_pattern(feedback)
    if pattern is None:
        logger.info("extraction_no_pattern", feedback_id=feedback_id)
        return
    
    # 检查相似 anti-pattern 是否已存在(避免重复)
    await _merge_or_save(pattern)
    logger.info("anti_pattern_created",
                pattern_id=pattern.pattern_id,
                trigger=pattern.trigger_summary[:60])


async def _merge_or_save(pattern: AntiPattern) -> None:
    """如果向量库已有相似 pattern,合并(累加 source);否则新建"""
    from athena.memory.store import find_similar_patterns
    
    similar = await find_similar_patterns(
        pattern.trigger_summary,
        top_k=1,
        min_similarity=0.85,
    )
    
    if similar:
        # 合并:把新 feedback id 加进 existing
        existing = similar[0].pattern
        existing.source_feedback_ids.extend(pattern.source_feedback_ids)
        existing.confidence = min(1.0, existing.confidence + 0.1)   # 重复出现 → 更可信
        await save_anti_pattern(existing)
    else:
        await save_anti_pattern(pattern)