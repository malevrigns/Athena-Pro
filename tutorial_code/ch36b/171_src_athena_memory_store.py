"""anti-pattern 的存储:向量索引 + 元数据"""
from __future__ import annotations
from langchain_openai import OpenAIEmbeddings
from athena.memory.schemas import AntiPattern, MemoryHit, MemoryQuery
from athena.store.checkpointer import get_pool

_embedder = OpenAIEmbeddings(model="text-embedding-3-small")


async def save_anti_pattern(pattern: AntiPattern) -> None:
    """保存到 Postgres,顺便生成 embedding"""
    # 用 trigger_summary 做 embedding key
    vector = await _embedder.aembed_query(pattern.trigger_summary)
    
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO anti_patterns (
                pattern_id, trigger_summary, trigger_keywords,
                failure_mode, correction, severity,
                source_feedback_ids, hit_count, last_hit_at,
                confidence, is_active, created_at, embedding
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
            )
            ON CONFLICT (pattern_id) DO UPDATE SET
                source_feedback_ids = EXCLUDED.source_feedback_ids,
                hit_count = EXCLUDED.hit_count,
                last_hit_at = EXCLUDED.last_hit_at,
                confidence = EXCLUDED.confidence,
                is_active = EXCLUDED.is_active
        """, pattern.pattern_id, pattern.trigger_summary,
            pattern.trigger_keywords, pattern.failure_mode,
            pattern.correction, pattern.severity,
            pattern.source_feedback_ids, pattern.hit_count,
            pattern.last_hit_at, pattern.confidence,
            pattern.is_active, pattern.created_at, vector)


async def find_similar_patterns(
    query: str,
    top_k: int = 3,
    min_similarity: float = 0.65,
) -> list[MemoryHit]:
    """语义检索 + 阈值过滤"""
    query_vec = await _embedder.aembed_query(query)
    
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                pattern_id, trigger_summary, trigger_keywords,
                failure_mode, correction, severity,
                source_feedback_ids, hit_count, last_hit_at,
                confidence, is_active, created_at,
                1 - (embedding <=> $1) AS similarity
            FROM anti_patterns
            WHERE is_active = TRUE
              AND confidence > 0.3
              AND 1 - (embedding <=> $1) > $2
            ORDER BY similarity DESC, severity DESC, confidence DESC
            LIMIT $3
        """, query_vec, min_similarity, top_k)
    
    return [
        MemoryHit(
            pattern=AntiPattern(**{k: v for k, v in row.items() if k != "similarity"}),
            similarity=row["similarity"],
        )
        for row in rows
    ]