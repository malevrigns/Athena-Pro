from typing import TypedDict
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

# ⚠️ 错误写法:messages 没有 reducer
class State(TypedDict):
    messages: list[AnyMessage]   # 普通 list,会被覆盖!

llm = ChatOpenAI(model="gpt-4o-mini")

def chat(state: State) -> dict:
    reply = llm.invoke(state["messages"])
    return {"messages": [reply]}   # 注意这里返回了一个新 list

builder = StateGraph(State)
builder.add_node("chat", chat)
builder.add_edge(START, "chat")
builder.add_edge("chat", END)
graph = builder.compile()

# 跑一次
result = graph.invoke({
    "messages": [HumanMessage(content="你好")]
})
print(len(result["messages"]))   # 期待 2(用户+AI),实际 1(只有 AI)!