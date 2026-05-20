from langchain.agents import initialize_agent
from langchain_openai import ChatOpenAI

agent = initialize_agent(
    tools=[search_tool, calculator_tool],
    llm=ChatOpenAI(model="gpt-4o-mini"),
    agent_type="zero-shot-react-description"
)

result = agent.run("帮我查一下北京今天天气,并告诉我适合穿什么")