"""HTTP + SSE + WebSocket 客户端"""
from __future__ import annotations
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import httpx_sse


class AthenaClient:
    def __init__(self, server_url: str, token: str | None):
        self.server_url = server_url.rstrip("/")
        self.token = token
        self._http: httpx.AsyncClient | None = None
    
    async def __aenter__(self):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self._http = httpx.AsyncClient(base_url=self.server_url, headers=headers,
                                        timeout=httpx.Timeout(60.0, read=None))
        return self
    
    async def __aexit__(self, *args):
        if self._http:
            await self._http.aclose()
    
    @asynccontextmanager
    async def _client(self):
        if self._http:
            yield self._http
        else:
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            async with httpx.AsyncClient(base_url=self.server_url,
                                          headers=headers,
                                          timeout=httpx.Timeout(60.0, read=None)) as c:
                yield c
    
    # ---------- task ----------
    async def create_task(self, question: str) -> dict:
        async with self._client() as c:
            r = await c.post("/v1/research", json={"question": question})
            r.raise_for_status()
            return r.json()
    
    async def stream_task(self, task_id: str) -> AsyncIterator[dict]:
        async with self._client() as c:
            async with httpx_sse.aconnect_sse(
                c, "GET", f"/v1/research/{task_id}/stream"
            ) as event_source:
                async for sse in event_source.aiter_sse():
                    if sse.event and sse.data:
                        data = json.loads(sse.data)
                        data["type"] = sse.event
                        yield data
    
    async def interrupt_task(self, task_id: str) -> None:
        async with self._client() as c:
            await c.post(f"/v1/research/{task_id}/interrupt")
    
    # ---------- session ----------
    async def list_tasks(self, limit: int = 20, status: str | None = None) -> list:
        async with self._client() as c:
            params = {"limit": limit}
            if status:
                params["status"] = status
            r = await c.get("/v1/tasks", params=params)
            r.raise_for_status()
            return r.json()
    
    async def export_task(self, task_id: str, fmt: str = "markdown"):
        async with self._client() as c:
            r = await c.get(f"/v1/tasks/{task_id}/export", params={"format": fmt})
            r.raise_for_status()
            return r.content if fmt == "pdf" else r.text
    
    # ---------- cost ----------
    async def get_monthly_cost(self) -> dict:
        async with self._client() as c:
            r = await c.get("/v1/cost/monthly")
            r.raise_for_status()
            return r.json()
    
    # ---------- permissions ----------
    async def list_permissions(self) -> list:
        async with self._client() as c:
            r = await c.get("/v1/permissions")
            return r.json()
    
    async def revoke_permission(self, decision_id: str) -> None:
        async with self._client() as c:
            await c.delete(f"/v1/permissions/{decision_id}")
    
    async def clear_session_permissions(self) -> None:
        async with self._client() as c:
            await c.delete("/v1/permissions", params={"scope": "session"})