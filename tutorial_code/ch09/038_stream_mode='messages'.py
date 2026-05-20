for msg_chunk, metadata in agent.stream(
    {"messages": [{"role": "user", "content": "写一个 100 字的故事"}]},
    stream_mode="messages"
):
    if msg_chunk.content:
        print(msg_chunk.content, end="", flush=True)