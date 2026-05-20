agent.invoke({"messages": [{"role": "user", "content": "我叫张三"}]})
# Agent: 你好,张三

agent.invoke({"messages": [{"role": "user", "content": "我叫什么名字?"}]})
# Agent: 抱歉,我不知道你的名字。  ← 完全不记得上次说过