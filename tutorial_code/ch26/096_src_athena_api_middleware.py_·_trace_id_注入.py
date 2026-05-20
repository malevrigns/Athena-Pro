"""FastAPI 中间件:每个请求注入 trace_id"""
from __future__ import annotations
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class TraceIdMiddleware(BaseHTTPMiddleware):
    """从请求 header 读 X-Trace-Id,没有就生成,注入到 structlog context。"""
    
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
        
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            path=request.url.path,
            method=request.method,
        )
        
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            structlog.contextvars.clear_contextvars()