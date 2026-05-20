from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph.message import add_messages

# 假设当前 state 里 messages 是这样
existing = [
    HumanMessage(content="你好", id="msg-1"),
    AIMessage(content="您好,有什么可以帮您?(此回复有错别字)", id="msg-2"),
]

# 节点要修正第二条
new = [
    AIMessage(content="您好,有什么可以帮您?", id="msg-2"),   # 同样的 id
]

result = add_messages(existing, new)
# 长度还是 2,但 msg-2 已被更新