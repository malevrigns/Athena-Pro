from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

llm = ChatOpenAI(model="gpt-4o-mini")

def chatbot(state: State) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}

builder = StateGraph(State)
builder.add_node("chatbot", chatbot)
builder.add_edge(START, "chatbot")
builder.add_edge("chatbot", END)
graph = builder.compile()

# 跑一次
result = graph.invoke({"messages": [HumanMessage(content="你好,请简单介绍自己")]})
for msg in result["messages"]:
    print(f"[{msg.__class__.__name__}] {msg.content}")