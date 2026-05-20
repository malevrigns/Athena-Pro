from typing import Annotated, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    plan: str

def make_plan(state: State):
    """LLM 生成一个执行计划。"""
    return {"plan": "我打算:1)删除旧数据  2)迁移新表  3)重启服务"}

def human_review(state: State):
    """暂停在这里,等人审核 plan。"""
    decision = interrupt({
        "question": "请审核以下计划,批准还是拒绝?",
        "plan": state["plan"],
    })
    # ↑ 上面 interrupt 之后,图会暂停
    # ↓ 当外部用 Command(resume=...) 恢复时,decision 就是传进来的值
    
    if decision.get("action") == "approve":
        return {"messages": [{"role": "ai", "content": "已批准,开始执行"}]}
    else:
        return {"messages": [{"role": "ai", "content": "已拒绝:" + decision.get("reason", "")}]}

def execute(state: State):
    return {"messages": [{"role": "ai", "content": "执行完毕"}]}

def route_after_review(state: State) -> str:
    last_msg = state["messages"][-1].content
    return END if "拒绝" in last_msg else "execute"

builder = StateGraph(State)
builder.add_node("plan", make_plan)
builder.add_node("review", human_review)
builder.add_node("execute", execute)
builder.add_edge(START, "plan")
builder.add_edge("plan", "review")
builder.add_conditional_edges("review", route_after_review)
builder.add_edge("execute", END)

# 编译时必须给 checkpointer
graph = builder.compile(checkpointer=InMemorySaver())

# ---------- 跑起来 ----------
config = {"configurable": {"thread_id": "session-1"}}

# 第一次 invoke:跑到 interrupt 处停下
result = graph.invoke({"messages": []}, config=config)
print("图已暂停。下一步:", graph.get_state(config).next)
# 下一步: ('review',)  ← 卡在 review 节点

# 模拟人类审核:批准
final = graph.invoke(
    Command(resume={"action": "approve"}),   # 关键!传入 resume
    config=config,
)
for msg in final["messages"]:
    print(msg.content)