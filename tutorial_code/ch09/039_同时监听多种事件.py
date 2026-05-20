for mode, payload in agent.stream(
    {"messages": [...]},
    stream_mode=["updates", "messages"]
):
    if mode == "updates":
        print(f"\n[节点完成] {list(payload.keys())}")
    elif mode == "messages":
        msg_chunk, meta = payload
        if msg_chunk.content:
            print(msg_chunk.content, end="", flush=True)