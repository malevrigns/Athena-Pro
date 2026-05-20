from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptAsset:
    name: str
    version: str
    template: str

    def render(self, **kwargs: object) -> str:
        return self.template.format(**kwargs)


PLANNER_PROMPT = PromptAsset(
    name="planner",
    version="2026-05-v5",
    template=(
        "用户问题: {question}\n"
        "请输出 3-5 个可并行调研的 topic。\n"
        "每个 topic 必须包含: title、question(具体到可被搜索)、rationale(为什么要查)、3 条 search_queries。\n"
        "用 JSON 数组返回,不要解释,不要 markdown 代码块标记。"
    ),
)

RESEARCHER_PROMPT = PromptAsset(
    name="researcher",
    version="2026-05-v5",
    template=(
        "主题: {title}\n"
        "调研问题: {question}\n"
        "以下是检索到的来源(标题 / URL / 摘要), 共 {source_count} 条:\n"
        "{sources_block}\n\n"
        "请基于来源做 4-6 句话的中文总结,语气克制、可引用,不要编造来源里没有的事实。"
    ),
)

REVIEWER_PROMPT = PromptAsset(
    name="reviewer",
    version="2026-05-v5",
    template=(
        "用户问题: {question}\n"
        "现有研究 findings 概要:\n{findings_block}\n\n"
        "请给出 1-3 条改进建议。每条建议必须以「补充: 」开头并指明应该搜索的新问题。"
        "如果你认为已经足够充分,请只输出一行 OK。"
    ),
)

WRITER_PROMPT = PromptAsset(
    name="writer",
    version="2026-05-v5",
    template=(
        "请基于以下 findings 用 Markdown 撰写一份正式研究报告。\n"
        "问题: {question}\n"
        "findings:\n{findings_block}\n\n"
        "报告结构: # 标题 / ## 摘要 / ## 关键结论 (要带 [n] 引用) / ## 详细分析 / ## 风险与建议 / ## 参考来源 (由系统填充, 不要重复)。\n"
        "正文使用中文,语气专业,引用一律使用 [数字] 的方式,数字会被系统替换。"
    ),
)
