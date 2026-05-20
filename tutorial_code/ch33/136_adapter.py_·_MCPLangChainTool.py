class MCPLangChainTool(BaseTool):
    """让 MCPTool 戴上 BaseTool 的壳。"""
    
    name: str
    description: str
    args_schema: Type[BaseModel]
    
    # 私有,绕过 Pydantic
    _client: MCPStdioClient
    _mcp_tool_name: str
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, client: MCPStdioClient, mcp_tool: MCPTool, **kwargs):
        args_model = _schema_to_pydantic_model(
            mcp_tool.qualified_name, mcp_tool.input_schema
        )
        super().__init__(
            name=mcp_tool.qualified_name,
            description=mcp_tool.description,
            args_schema=args_model,
            **kwargs,
        )
        # 用 object.__setattr__ 绕过 BaseTool 字段限制
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_mcp_tool_name", mcp_tool.name)
    
    def _run(self, **kwargs):
        raise NotImplementedError("MCP tools are async-only")
    
    async def _arun(self, **kwargs) -> str:
        """LangChain 调用工具时走的路径。"""
        result = await self._client.call_tool(self._mcp_tool_name, kwargs)
        # MCP 返回 {"content": [{"type": "text", "text": "..."}, ...]}
        # 我们简单拼接所有 text 块
        parts: list[str] = []
        for item in result.get("content", []):
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif item.get("type") == "image":
                parts.append(f"[image: {item.get('mimeType', '?')}]")
        return "\n".join(parts)