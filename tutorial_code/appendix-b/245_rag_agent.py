"""
带知识库检索的 Agent。
"""
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langgraph.prebuilt import create_react_agent

# 假设你已经建好了向量库
embeddings = OpenAIEmbeddings()
vectorstore = FAISS.load_local("./knowledge_base", embeddings,
                                allow_dangerous_deserialization=True)

@tool
def search_knowledge_base(query: str, k: int = 3) -> str:
    """从公司内部知识库搜索相关文档。
    
    Args:
        query: 自然语言查询
        k: 返回多少条结果,默认 3
    """
    docs = vectorstore.similarity_search(query, k=k)
    return "\n\n".join([f"【文档 {i+1}】\n{d.page_content}" 
                        for i, d in enumerate(docs)])

agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[search_knowledge_base],
    prompt=(
        "你是公司内部知识助手。回答问题前必须先用 search_knowledge_base "
        "检索相关文档,基于检索结果回答。不要凭空回答。"
    ),
)