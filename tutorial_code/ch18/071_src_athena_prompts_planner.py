"""
Planner 的 Prompt 资产。

每个 Prompt 是一个带 version 的 dataclass,改动时务必:
1. 升 version 号
2. 在 tests/eval/dataset.jsonl 加新样本
3. 跑 `make eval` 看分数有没有下降
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerPrompt:
    version: str
    system: str
    
    def __str__(self) -> str:
        return self.system


PLANNER_V1 = PlannerPrompt(
    version="planner.v1.2026-05",
    system="""你是一名资深研究规划师,服务于一个企业级研究情报平台。

【你的任务】
把用户的研究问题拆解为 {min_topics}-{max_topics} 个独立的子研究方向。

【拆解原则】
1. **互不重叠**:子方向之间应明确边界,避免内容重复
2. **可独立调研**:每个子方向不依赖其他方向的结论才能展开
3. **共同覆盖**:所有子方向加起来,应能完整回答原问题
4. **抽象层次一致**:不要 1 个粗 4 个细,要么都粗要么都细
5. **可操作**:每个子方向应能转化为具体的搜索查询

【避免的反模式】
- ✗ "概述与背景" → 太泛,无法搜索
- ✗ "相关公司列表" + "主要公司分析" → 重叠
- ✗ "技术细节" + "性能数据" + "成本分析" → 抽象层次不一致

{revision_context}

【输出格式】
你必须以结构化方式输出,字段:
- sub_topics: 子方向列表,每项含 id (snake_case), topic (中文一句话), why (为何要研究它)
- rationale: 整体拆解逻辑的说明
""",
)


def render_planner_prompt(
    min_topics: int = 4,
    max_topics: int = 6,
    revision_feedback: str | None = None,
    completed_topics: list[str] | None = None,
) -> str:
    """渲染 Planner Prompt。
    
    revision_feedback 不为 None 时,意味着是"基于反馈再规划",
    Prompt 会被注入一段"已研究过什么、为何要补"的上下文。
    """
    if revision_feedback:
        revision_context = (
            f"\n【重要:这是修订规划】\n"
            f"上一轮研究后,审稿员给出反馈:\n"
            f">>> {revision_feedback}\n\n"
            f"已研究过的方向(不要重复):\n"
            + "\n".join(f"  - {t}" for t in (completed_topics or []))
            + "\n\n请基于反馈,生成 1-3 个补充子方向。\n"
        )
    else:
        revision_context = ""
    
    return PLANNER_V1.system.format(
        min_topics=min_topics,
        max_topics=max_topics,
        revision_context=revision_context,
    )