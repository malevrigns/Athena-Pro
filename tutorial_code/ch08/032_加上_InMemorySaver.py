from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[],
    checkpointer=InMemorySaver(),    # ← 关键
)

# 必须给每次调用指定 thread_id
config = {"configurable": {"thread_id": "user-42"}}

agent.invoke(
    {"messages": [{"role": "user", "content": "我叫张三"}]},
    config=config,
)

# 同一个 thread_id,会自动加载历史
result = agent.invoke(
    {"messages": [{"role": "user", "content": "我叫什么名字?"}]},
    config=config,
)
print(result["messages"][-1].content)
# 你叫张三。