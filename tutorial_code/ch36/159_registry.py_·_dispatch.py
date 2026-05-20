async def dispatch_subagent(
    agent_type: str, task: str, max_iterations: int = 10
) -> str:
    """实际派发 subagent。"""
    spec = SUBAGENT_REGISTRY.get(agent_type)
    if not spec:
        return f"❌ 未知 subagent 类型:{agent_type}"
    
    from langgraph.prebuilt import create_react_agent
    from athena.llm_factory import get_llm
    from athena.subagents.runner import run_isolated
    
    # 关键:用 create_react_agent 创建一个独立 graph
    # 它有自己的 messages 历史,完全不接触主 Agent 的 state
    tools = spec.tools_factory()
    sub_graph = create_react_agent(
        model=get_llm(model=spec.model, node_name=f"subagent.{agent_type}"),
        tools=tools,
        prompt=spec.system_prompt,
    )
    
    return await run_isolated(sub_graph, task, max_iterations)