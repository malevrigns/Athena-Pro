# 定义工具
@tool
def my_tool(arg: str) -> str:
    """工具的清晰描述。"""
    return f"result for {arg}"

# 绑给 LLM
llm = ChatOpenAI(model="gpt-4o-mini").bind_tools([my_tool])

# 用 ToolNode 执行
tool_node = ToolNode([my_tool], handle_tool_errors=True)

# 标准 ReAct 循环
builder.add_node("llm", lambda s: {"messages": [llm.invoke(s["messages"])]})
builder.add_node("tools", tool_node)
builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", tools_condition)
builder.add_edge("tools", "llm")