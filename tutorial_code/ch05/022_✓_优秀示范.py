@tool
def web_search(query: str, max_results: int = 5) -> str:
    """搜索互联网获取信息。适合查找最新事件、人物背景、技术资料。
    
    Args:
        query: 搜索查询,建议 3-8 个关键词。例如 "LangGraph 多 Agent 教程"
               不要用完整问句(如 "请告诉我..."),用关键词组合效果更好。
        max_results: 返回结果数,默认 5。需要详尽信息时可调到 10。
    
    Returns:
        多条搜索结果拼接的文本,每条结果用 --- 分隔,
        包含标题、URL、摘要。
    
    Example:
        web_search("Python 异步编程 教程", 3)
        → "[1] 标题: ... URL: ... 摘要: ...\n---\n[2] ..."
    
    Note:
        - 不支持图片、视频搜索,只搜文本网页
        - 中文英文都支持
        - 单次调用约 2 秒
    """
    ...