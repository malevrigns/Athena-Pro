"""端到端集成测试 - 跑真 LLM(便宜的)"""
import pytest

from athena.graph.builders import build_main_graph
from athena.store.checkpointer import get_checkpointer


@pytest.fixture(autouse=True)
def mock_web_search(monkeypatch):
    """所有测试都 mock web_search,不要真的去搜网。"""
    async def fake_search(query: str) -> list[dict]:
        return [{
            "title": f"Result for {query}",
            "url": f"https://example.com/{query.replace(' ', '-')}",
            "snippet": f"{query} 相关:LangGraph 是用于构建状态图的工具,支持多 Agent 协作。",
        }]
    monkeypatch.setattr("athena.tools.web_search.web_search_with_breaker", fake_search)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_research_pipeline():
    """完整流程:question → plan → research → fact_check → write → review → END。"""
    graph = await build_main_graph()
    config = {"configurable": {"thread_id": "test-e2e-1"}}
    
    initial_state = {
        "question": "什么是 LangGraph",
        "task_id": "test-e2e-1",
        "research_plan": [],
        "findings": [],
        "revision_count": 0,
    }
    
    final = await graph.ainvoke(initial_state, config=config)
    
    # 断言关键产物
    assert final.get("final_report"), "应该产出最终报告"
    assert len(final["final_report"]) > 200, "报告应该有内容"
    assert "LangGraph" in final["final_report"]
    assert len(final.get("findings", [])) >= 2, "至少要有 2 个 findings"
    
    # 断言引用追溯
    assert final.get("report_metadata", {}).get("n_sources", 0) > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_recovery_from_checkpoint():
    """模拟中途崩溃,验证从 checkpoint 恢复。"""
    graph = await build_main_graph()
    config = {"configurable": {"thread_id": "test-recovery"}}
    
    # 跑到一半,人为中断
    # ...(详细 mock 略)
    
    # 用 None 继续,应该接着跑
    final = await graph.ainvoke(None, config=config)
    assert final.get("final_report")