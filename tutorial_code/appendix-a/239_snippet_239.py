# updates 模式:最常用
for chunk in graph.stream(inputs, stream_mode="updates"):
    for node, update in chunk.items():
        print(f"[{node}] {update}")

# messages 模式:token 流
for msg_chunk, meta in graph.stream(inputs, stream_mode="messages"):
    print(msg_chunk.content, end="", flush=True)

# 异步
async for chunk in graph.astream(inputs, stream_mode="updates"):
    ...