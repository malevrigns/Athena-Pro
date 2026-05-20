    async def stop(self) -> None:
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.proc.kill()                        # 5 秒还不退就强杀
        if self._reader_task:
            self._reader_task.cancel()
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用 server 上的工具,返回结果 content。"""
        if not self._initialized:
            raise RuntimeError(f"MCP server {self.config.name} not initialized")
        
        result = await self._request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        return result