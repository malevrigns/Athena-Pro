"""
主模型失败时降级到备用模型。
"""
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

primary = ChatOpenAI(model="gpt-4o-mini")
backup1 = ChatOpenAI(model="gpt-3.5-turbo")
backup2 = ChatAnthropic(model="claude-3-haiku-20240307")

# 组合:重试 + 降级
robust_llm = (
    primary
    .with_retry(stop_after_attempt=2, wait_exponential_jitter=True)
    .with_fallbacks([backup1, backup2])
)

# 在图节点里用 robust_llm 代替 primary
def my_node(state):
    return {"messages": [robust_llm.invoke(state["messages"])]}