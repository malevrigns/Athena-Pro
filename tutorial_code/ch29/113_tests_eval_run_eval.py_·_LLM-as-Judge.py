"""跑整个评估集,产出质量报告"""
from __future__ import annotations
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, conint

from athena.graph.builders import build_main_graph

JUDGE_MODEL = "gpt-4o"                                # 用更强的当裁判


class JudgeVerdict(BaseModel):
    """裁判对单个报告的评分。"""
    coverage: conint(ge=1, le=10)                    = Field(..., description="问题覆盖度")
    accuracy: conint(ge=1, le=10)                    = Field(..., description="事实准确性")
    structure: conint(ge=1, le=10)                   = Field(..., description="结构清晰度")
    citation_quality: conint(ge=1, le=10)            = Field(..., description="引用质量")
    hallucination_severity: conint(ge=0, le=10)      = Field(..., description="幻觉严重度,0=无")
    overall: conint(ge=1, le=10)                     = Field(..., description="综合评分")
    reasoning: str                                    = Field(..., description="评分理由")


@dataclass
class EvalCase:
    id: str
    question: str
    expected_topics: list[str]
    max_cost_usd: float = 0.30


async def evaluate_one(graph, judge, case: EvalCase) -> dict:
    """跑一个 case,让 judge 评分。"""
    config = {"configurable": {"thread_id": f"eval-{case.id}"}}
    
    initial = {
        "question": case.question,
        "task_id": f"eval-{case.id}",
        "research_plan": [],
        "findings": [],
        "revision_count": 0,
    }
    
    import time
    t0 = time.perf_counter()
    final = await graph.ainvoke(initial, config=config)
    duration = time.perf_counter() - t0
    
    # 让 judge 评分
    verdict = await judge.ainvoke([
        {"role": "system", "content": (
            "你是研究报告评审专家。给以下报告打分(1-10)。"
            "特别注意:幻觉指报告中无法在 sources 中找到证据的论断。"
        )},
        {"role": "user", "content": (
            f"原始问题:{case.question}\n\n"
            f"期望覆盖的子主题:{case.expected_topics}\n\n"
            f"报告:\n{final.get('final_report', '(无报告)')}\n\n"
            f"sources:\n{json.dumps([f.get('sources_full', []) for f in final.get('findings', [])], ensure_ascii=False)[:3000]}"
        )},
    ])
    
    cost = final.get("cost_ledger", {}).get("spent_usd", 0)
    
    return {
        "id": case.id,
        "question": case.question,
        "duration_sec": round(duration, 1),
        "cost_usd": round(cost, 4),
        "cost_overrun": cost > case.max_cost_usd,
        "verdict": verdict.model_dump(),
    }


async def main(dataset_path: Path, output_path: Path):
    cases = [
        EvalCase(**json.loads(line))
        for line in dataset_path.read_text().splitlines() if line.strip()
    ]
    
    graph = await build_main_graph()
    judge = ChatOpenAI(model=JUDGE_MODEL, temperature=0).with_structured_output(JudgeVerdict)
    
    # 并发跑,但限制并发数
    sem = asyncio.Semaphore(5)
    async def gated_eval(c):
        async with sem:
            return await evaluate_one(graph, judge, c)
    
    results = await asyncio.gather(*[gated_eval(c) for c in cases])
    
    # 汇总指标
    avg_overall = sum(r["verdict"]["overall"] for r in results) / len(results)
    avg_hallucination = sum(r["verdict"]["hallucination_severity"] for r in results) / len(results)
    avg_cost = sum(r["cost_usd"] for r in results) / len(results)
    
    print(f"=== Eval Summary ===")
    print(f"Avg overall:       {avg_overall:.2f} / 10")
    print(f"Avg hallucination: {avg_hallucination:.2f} / 10 (lower is better)")
    print(f"Avg cost:          ${avg_cost:.4f}")
    print(f"P95 cost:          ${sorted(r['cost_usd'] for r in results)[int(len(results)*0.95)]:.4f}")
    
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main(
        Path("tests/eval/dataset.jsonl"),
        Path("eval_results.json"),
    ))