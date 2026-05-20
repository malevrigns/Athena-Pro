from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
tools = [get_weather, calculator]
llm_with_tools = llm.bind_tools(tools)   # 给 LLM 装上"工具能力"

# 现在调用 LLM 时,它知道有这两个工具可用
response = llm_with_tools.invoke("北京天气怎么样")
print(response.tool_calls)
# [{'name': 'get_weather', 'args': {'city': '北京'}, 'id': 'call_abc123', 'type': 'tool_call'}]