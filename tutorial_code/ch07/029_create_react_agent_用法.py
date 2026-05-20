from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

@tool
def get_weather(city: str) -> str:
    """获取某城市天气。"""
    return f"{city}:晴,15°C"

@tool
def multiply(a: float, b: float) -> float:
    """计算两数相乘。"""
    return a * b

# ↓↓↓ 上一章那 30 行的图,现在变成一行 ↓↓↓
agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
    tools=[get_weather, multiply],
    prompt="你是一个简洁、有帮助的助手。需要时主动调用工具。",
)

# 用法和图一样
result = agent.invoke({
    "messages": [{"role": "user", "content": "17 乘 23 等于多少?北京天气如何?"}]
})

print(result["messages"][-1].content)