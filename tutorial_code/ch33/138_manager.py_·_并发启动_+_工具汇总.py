    async def start_all(self) -> None:
        """并发启动所有 server,失败的不影响其他。"""
        import asyncio
        results = await asyncio.gather(
            *[self._safe_start(name, c) for name, c in self.clients.items()],
            return_exceptions=False,                  # 异常已在 _safe_start 吃掉
        )
        # 合并所有 server 的工具
        for client in self.clients.values():
            if client._initialized:
                for mcp_tool in client.tools:
                    self.tools.append(MCPLangChainTool(client, mcp_tool))
        logger.info("mcp_manager_ready", servers=len(self.clients),
                    total_tools=len(self.tools))
    
    async def _safe_start(self, name: str, client: MCPStdioClient) -> bool:
        try:
            await client.start()
            return True
        except Exception as e:
            logger.exception("mcp_server_start_failed", server=name, error=str(e))
            return False
    
    async def stop_all(self) -> None:
        import asyncio
        await asyncio.gather(
            *[c.stop() for c in self.clients.values()],
            return_exceptions=True,
        )