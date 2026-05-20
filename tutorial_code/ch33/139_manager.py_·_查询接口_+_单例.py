    def get_tools(self) -> list[BaseTool]:
        return list(self.tools)
    
    def get_permission_policy(self, tool_qualified_name: str) -> str:
        """tool 名格式 'server__toolname',找回它所属 server 的策略。"""
        server_name = tool_qualified_name.split("__", 1)[0]
        client = self.clients.get(server_name)
        if not client:
            return "ask"
        return client.config.permission_policy


# 全局单例
_manager: MCPManager | None = None

async def get_mcp_manager() -> MCPManager:
    global _manager
    if _manager is None:
        _manager = MCPManager.from_config_file()
        await _manager.start_all()
    return _manager