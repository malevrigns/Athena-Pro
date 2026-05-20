async def build_researcher_tools() -> list:
    """Researcher 的工具 = 本地工具 + 所有 MCP server 暴露的工具"""
    from athena.mcp.manager import get_mcp_manager
    from athena.tools.search import web_search
    from athena.tools.sandbox_tools import python_repl, bash_tool
    
    local_tools = [web_search, python_repl, bash_tool]
    mcp = await get_mcp_manager()
    return local_tools + mcp.get_tools()