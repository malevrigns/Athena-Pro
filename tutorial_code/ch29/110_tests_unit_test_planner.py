"""测试 Planner 节点 - 完全 mock,不调真 LLM"""
import pytest
from unittest.mock import patch, MagicMock

from athena.agents.planner import planner_node


@pytest.fixture
def fake_planner_response():
    """模拟 LLM 输出的 ResearchPlan。"""
    response = MagicMock()
    response.sub_topics = ["主题A", "主题B", "主题C"]
    response.rationale = "拆解理由"
    return response


@pytest.mark.asyncio
async def test_planner_first_call(fake_planner_response):
    """首次规划:不带 review_feedback。"""
    state = {"question": "调研 LangGraph", "review_feedback": ""}
    
    with patch("athena.agents.planner.get_llm") as mock_get_llm:
        # 让 LLM.with_structured_output().invoke() 返回 fake response
        llm = MagicMock()
        llm.with_structured_output.return_value.invoke.return_value = fake_planner_response
        mock_get_llm.return_value = llm
        
        cmd = await planner_node(state)
    
    # 断言:正确把 sub_topics 写入 state
    assert cmd.goto in ("supervisor", "plan_review")
    assert cmd.update["research_plan"] == ["主题A", "主题B", "主题C"]


@pytest.mark.asyncio
async def test_planner_revision(fake_planner_response):
    """带 review_feedback 时:Prompt 里要带上"修订上下文"。"""
    state = {
        "question": "调研 LangGraph",
        "review_feedback": "缺少安全性维度",
        "findings": [{"topic": "性能优化", "summary": "..."}],
    }
    
    with patch("athena.agents.planner.get_llm") as mock_get_llm:
        llm = MagicMock()
        llm.with_structured_output.return_value.invoke.return_value = fake_planner_response
        mock_get_llm.return_value = llm
        
        await planner_node(state)
        
        # 检查传给 LLM 的 prompt 包含"修订"信息
        invoke_args = llm.with_structured_output.return_value.invoke.call_args
        prompt_messages = invoke_args[0][0]
        prompt_text = " ".join(m["content"] for m in prompt_messages)
        assert "缺少安全性维度" in prompt_text
        assert "性能优化" in prompt_text                 # 已研究过的


@pytest.mark.asyncio
async def test_supervisor_dispatches_pending_topics():
    """Supervisor 应该派出未完成的 topic 给 researcher。"""
    from athena.agents.supervisor import supervisor_node
    
    state = {
        "research_plan": ["A", "B", "C"],
        "findings": [{"topic": "A", "summary": "...", "is_failed": False}],
    }
    
    cmd = await supervisor_node(state)
    
    # 应该派 B 和 C(还没完成)给 researcher 并行跑
    assert cmd.goto == "researcher" or isinstance(cmd.goto, list)