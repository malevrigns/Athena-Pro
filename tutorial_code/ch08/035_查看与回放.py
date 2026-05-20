config = {"configurable": {"thread_id": "alice"}}

# 当前状态
state = agent.get_state(config)
print(state.values)        # 状态字典
print(state.next)          # 下一个要执行的节点
print(state.config)        # 完整 config(含 checkpoint_id)

# 历史快照(每个 checkpoint 一个)
for snapshot in agent.get_state_history(config):
    print(snapshot.config["configurable"]["checkpoint_id"], 
          "→", list(snapshot.values.keys()))

# 时间旅行:从某个历史点重新开始
old_config = list(agent.get_state_history(config))[3].config
agent.invoke(None, config=old_config)   # 从那个点继续