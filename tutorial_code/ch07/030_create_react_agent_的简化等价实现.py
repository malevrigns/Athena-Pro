def create_react_agent_simplified(model, tools, prompt=None, checkpointer=None):
    """这是 create_react_agent 的核心逻辑(去掉了一些可选特性)。"""
    
    # 1. 给 LLM 绑工具
    llm_with_tools = model.bind_tools(tools)
    
    # 2. 定义 state schema(默认就是 MessagesState)
    class AgentState(MessagesState):
        pass
    
    # 3. 定义 LLM 节点
    def call_model(state: AgentState):
        # 如果有 prompt,加在最前面
        messages = state["messages"]
        if prompt:
            if isinstance(prompt, str):
                messages = [{"role": "system", "content": prompt}, *messages]
            elif callable(prompt):
                messages = prompt(state)
            # ... 还有其他形式的 prompt
        return {"messages": [llm_with_tools.invoke(messages)]}
    
    # 4. 工具节点(自带错误处理)
    tool_node = ToolNode(tools, handle_tool_errors=True)
    
    # 5. 路由函数:有 tool_calls 去 tools,否则结束
    def should_continue(state):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END
    
    # 6. 建图
    builder = StateGraph(AgentState)
    builder.add_node("agent", call_model)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue)
    builder.add_edge("tools", "agent")
    
    return builder.compile(checkpointer=checkpointer)