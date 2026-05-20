"""
最简单的 LangGraph 应用:接收问题,调用 LLM,返回答案。
"""
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

# ---------- 1. 定义状态 ----------
class State(TypedDict):
    question: str   # 输入:用户的问题
    answer: str     # 输出:LLM 的回答

# ---------- 2. 初始化 LLM ----------
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ---------- 3. 定义节点 ----------
def llm_node(state: State) -> dict:
    """这个节点的工作:把 state 里的 question 喂给 LLM,把回答放进 state。"""
    response = llm.invoke(state["question"])
    return {"answer": response.content}

# ---------- 4. 建图 ----------
builder = StateGraph(State)
builder.add_node("llm", llm_node)
builder.add_edge(START, "llm")
builder.add_edge("llm", END)
graph = builder.compile()

# ---------- 5. 运行 ----------
if __name__ == "__main__":
    result = graph.invoke({"question": "用一句话解释什么是量子纠缠"})
    print("问题:", result["question"])
    print("回答:", result["answer"])