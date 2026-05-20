from langgraph.prebuilt import ToolNode

tool_node = ToolNode(tools, handle_tool_errors=True)
# handle_tool_errors=True:工具抛异常时不崩溃,把错误信息作为 ToolMessage 返回