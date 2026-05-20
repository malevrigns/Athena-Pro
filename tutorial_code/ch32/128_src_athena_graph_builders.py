from athena.tools.sandbox_tools import python_repl, bash_tool
from athena.tools.search import web_search

researcher_tools = [
    web_search,              # 走主进程
    python_repl,             # 进沙箱
    bash_tool,               # 进沙箱 + 权限审批
]

# create_react_agent 也好,自己写也好,工具列表里直接加就行
researcher_agent = create_react_agent(
    model=get_llm(),
    tools=researcher_tools,
    # ToolNode 替换为 GuardedToolNode
)