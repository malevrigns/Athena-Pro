result = graph.invoke({
    "messages": [HumanMessage(content="北京天气怎么样?另外 23*7 等于多少?")]
})

# 把整个对话过程打印出来
for msg in result["messages"]:
    print(f"[{msg.__class__.__name__}]")
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        for tc in msg.tool_calls:
            print(f"  调用工具: {tc['name']}({tc['args']})")
    else:
        print(f"  {msg.content}")