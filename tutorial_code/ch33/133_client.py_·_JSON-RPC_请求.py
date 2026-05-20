    async def _request(self, method: str, params: dict, timeout: float = 30) -> Any:
        """发请求,等响应。"""
        msg_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self.pending[msg_id] = future                  # 把 future 挂到等待区
        
        payload = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
        await self._write(payload)
        
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self.pending.pop(msg_id, None)             # 不管成功失败都要清理
    
    async def _notify(self, method: str, params: dict) -> None:
        """发通知,不等响应。"""
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})
    
    async def _write(self, payload: dict) -> None:
        line = json.dumps(payload) + "\n"
        self.proc.stdin.write(line.encode())
        await self.proc.stdin.drain()