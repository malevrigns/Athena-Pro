config_alice = {"configurable": {"thread_id": "alice"}}
config_bob   = {"configurable": {"thread_id": "bob"}}

agent.invoke({"messages": [{"role": "user", "content": "我叫 Alice"}]}, config_alice)
agent.invoke({"messages": [{"role": "user", "content": "我叫 Bob"}]}, config_bob)

# Alice 的会话和 Bob 完全独立
agent.invoke({"messages": [{"role": "user", "content": "我叫什么"}]}, config_alice)
# → "你叫 Alice"
agent.invoke({"messages": [{"role": "user", "content": "我叫什么"}]}, config_bob)
# → "你叫 Bob"