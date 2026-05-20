from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_openai import ChatOpenAI

agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[],
    prompt="你是友好的助手。",
    checkpointer=InMemorySaver(),
)

config = {"configurable": {"thread_id": "user-1"}}

while True:
    user_input = input("你: ")
    if user_input.lower() in ("quit", "exit"):
        break
    result = agent.invoke({"messages": [{"role": "user", "content": user_input}]},
                          config=config)
    print("AI:", result["messages"][-1].content)