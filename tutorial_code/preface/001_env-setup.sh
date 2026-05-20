# ① Python 3.10 或更高(3.9 已不支持)
python --version    # 应该 ≥ 3.10

# ② 装包(总共大约 30 秒)
pip install -U langgraph langchain langchain-openai
pip install -U langgraph-checkpoint-sqlite

# ③ 设置 API Key
export OPENAI_API_KEY="sk-..."         # macOS / Linux
# set OPENAI_API_KEY=sk-...            # Windows CMD
# $env:OPENAI_API_KEY="sk-..."         # Windows PowerShell

# ④ 验证装好了
python -c "from langgraph.graph import StateGraph; print('OK')"