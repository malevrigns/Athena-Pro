from typing import TypedDict
from langgraph.graph import StateGraph, START, END

# 1. 定义 State
class State(TypedDict):
    question: str
    answer: str

# 2. 定义节点函数
def answer_node(state: State) -> dict:
    return {"answer": f"关于「{state['question']}」,我说:42"}

# 3. 建图
builder = StateGraph(State)            # 创建图,告诉它 State 的结构
builder.add_node("answer", answer_node) # 添加一个节点,名字叫 "answer"
builder.add_edge(START, "answer")      # 从入口走到 "answer"
builder.add_edge("answer", END)        # 从 "answer" 走到出口

# 4. 编译(必须!)
graph = builder.compile()

# 5. 运行
result = graph.invoke({"question": "生命的意义是什么"})
print(result)
# {'question': '生命的意义是什么', 'answer': '关于「生命的意义是什么」,我说:42'}