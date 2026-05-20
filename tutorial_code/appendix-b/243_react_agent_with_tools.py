from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

@tool
def search(query: str) -> str:
    """搜索互联网获取信息。"""
    # TODO: 接入真实 API
    return f"模拟搜索结果: {query}"

@tool
def calculator(expression: str) -> str:
    """计算数学表达式。例如 '2 + 3 * 4'"""
    return str(eval(expression, {"__builtins__": {}}))

agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
    tools=[search, calculator],
    prompt="你是一个能搜索和计算的助手。",
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "搜索 LangGraph,然后算 3*7+2"}]
})
print(result["messages"][-1].content)