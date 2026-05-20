for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "北京天气?23*7?"}]},
    stream_mode="updates"
):
    for node_name, update in chunk.items():
        print(f"\n=== 节点 [{node_name}] 完成 ===")
        for msg in update.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"  → 调用 {tc['name']}({tc['args']})")
            elif msg.__class__.__name__ == "ToolMessage":
                print(f"  ← 工具返回: {msg.content[:80]}")
            else:
                print(f"  AI: {msg.content[:100]}")