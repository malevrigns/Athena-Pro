from langgraph.checkpoint.memory import InMemorySaver

graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "session-001"}}

# 跑(自动存档)
graph.invoke(inputs, config=config)

# 查状态
state = graph.get_state(config)
print(state.values)   # 当前 state
print(state.next)     # 下一步会跑哪个节点

# 历史
for snap in graph.get_state_history(config):
    print(snap.config, snap.values)

# 时间旅行
old_config = list(graph.get_state_history(config))[2].config
graph.invoke(None, config=old_config)   # 从旧节点继续