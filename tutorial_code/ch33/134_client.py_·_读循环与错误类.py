    async def _read_loop(self) -> None:
        """持续读 stdout,分发响应到对应 future。"""
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                logger.warning("mcp_eof", server=self.config.name)
                break                                     # server 退出了
            try:
                msg = json.loads(line.decode())
            except json.JSONDecodeError:
                logger.error("mcp_invalid_json", server=self.config.name,
                             raw=line[:200])
                continue                                   # 坏帧丢掉,继续读
            
            # 响应:有 id 的消息,送给对应 future
            if msg_id := msg.get("id"):
                future = self.pending.get(str(msg_id))
                if future and not future.done():
                    if "error" in msg:
                        future.set_exception(MCPError(msg["error"]))
                    else:
                        future.set_result(msg.get("result"))
            # 通知:有 method 没 id(目前 Athena 暂不处理 server 主动发来的通知)
    
    async def _stderr_loop(self) -> None:
        """把 server 的 stderr 转发到日志。"""
        while True:
            line = await self.proc.stderr.readline()
            if not line:
                break
            logger.debug("mcp_server_stderr", server=self.config.name,
                         line=line.decode().rstrip())


class MCPError(Exception):
    def __init__(self, error: dict):
        self.code = error.get("code")
        self.message = error.get("message", "MCP error")
        self.data = error.get("data")
        super().__init__(f"[{self.code}] {self.message}")