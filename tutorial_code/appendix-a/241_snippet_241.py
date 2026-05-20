from langgraph.types import interrupt, Command

def review_node(state):
    decision = interrupt({"question": "approve?"})
    return {"approved": decision == "yes"}

# 必须有 checkpointer
graph = builder.compile(checkpointer=InMemorySaver())

# 第一次:跑到 interrupt 处停
result = graph.invoke(inputs, config=config)

# 检查 state.next 是否含 "review_node"
state = graph.get_state(config)

# 恢复
graph.invoke(Command(resume="yes"), config=config)