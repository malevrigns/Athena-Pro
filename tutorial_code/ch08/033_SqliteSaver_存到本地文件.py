from langgraph.checkpoint.sqlite import SqliteSaver

# 上下文管理器形式(推荐,会自动关闭连接)
with SqliteSaver.from_conn_string("checkpoints.db") as memory:
    agent = create_react_agent(
        model=ChatOpenAI(model="gpt-4o-mini"),
        tools=[],
        checkpointer=memory,
    )
    
    config = {"configurable": {"thread_id": "user-42"}}
    agent.invoke({"messages": [...]}, config=config)

# 程序退出后,checkpoints.db 文件里保存了完整状态
# 下次再启动程序,用同一个 thread_id 还能继续