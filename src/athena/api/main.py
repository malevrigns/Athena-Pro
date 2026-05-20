from __future__ import annotations

import asyncio
import hmac
import json
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

from athena.api.schemas import (
    ConfigSnapshot,
    CreateTaskRequest,
    CreateTaskResponse,
    ExportResponse,
    FeedbackRequest,
    HealthResponse,
    InterruptResponse,
    ReviewRequest,
)
from athena.config import get_settings
from athena.export import ExportError, available_formats, get_exporter
from athena.memory import Feedback, MemoryStore
from athena.observability import configure_logging, logger
from athena.persistence import get_store
from athena.runtime import runtime_store
from athena.schemas import TaskStatus

API_VERSION = "5.0.0"

_memory_store = MemoryStore()
_start_time = time.monotonic()


# ---------- Auth (single-user bearer token) ----------

async def _verify_auth(request: Request) -> None:
    settings = get_settings()
    if not settings.require_auth:
        return
    # Static assets / health are open by design — handled in middleware below.
    expected = settings.api_key
    if not expected:
        # In a non-dev env with no key configured, refuse rather than open the door.
        raise HTTPException(status_code=503, detail="server not configured: ATHENA_API_KEY missing")
    header = request.headers.get("authorization", "")
    token = ""
    if header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="invalid or missing api key")


# ---------- Rate limit (simple sliding window per IP) ----------

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_per_minute: int) -> None:
        super().__init__(app)
        self.max_per_minute = max_per_minute
        self.window: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable]):
        if request.url.path in {"/health", "/v1/config"}:
            return await call_next(request)
        # Be lenient with SSE stream — it stays open by design.
        if request.url.path.endswith("/stream"):
            return await call_next(request)
        key = (request.client.host if request.client else "unknown") + ":" + request.url.path
        now = time.monotonic()
        bucket = self.window[key]
        while bucket and now - bucket[0] > 60.0:
            bucket.popleft()
        if len(bucket) >= self.max_per_minute:
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        bucket.append(now)
        return await call_next(request)


# ---------- App factory ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    await runtime_store.ensure_started()
    logger.info("athena.startup version=%s provider=%s env=%s", API_VERSION, settings.llm_provider, settings.env)
    yield
    store = get_store()
    await store.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Athena Pro API", version=API_VERSION, lifespan=lifespan)

    origins = list(settings.allowed_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, max_per_minute=settings.rate_limit_per_minute)

    # Auxiliary routers
    from athena.api.cost import router as cost_router
    from athena.api.citations import router as cite_router
    from athena.api.knowledge import router as kn_router
    from athena.api.misc import router as misc_router
    from athena.api.notifications import router as notification_router
    app.include_router(cost_router, dependencies=[Depends(_verify_auth)])
    app.include_router(cite_router, dependencies=[Depends(_verify_auth)])
    app.include_router(kn_router, dependencies=[Depends(_verify_auth)])
    app.include_router(notification_router, dependencies=[Depends(_verify_auth)])
    app.include_router(misc_router)  # announcements open by design

    auth_dep = Depends(_verify_auth)

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(
            ok=True,
            version=API_VERSION,
            uptime_sec=round(time.monotonic() - _start_time, 2),
            llm_provider=settings.llm_provider,
            search_provider=settings.search_provider,
            db_path=str(settings.sqlite_path or ""),
            extras={"export_formats": available_formats()},
        )

    @app.get("/v1/config", response_model=ConfigSnapshot)
    async def get_config():
        return ConfigSnapshot(
            env=settings.env,
            llm_provider=settings.llm_provider,
            default_model=settings.default_model,
            search_provider=settings.search_provider,
            quality_threshold=settings.quality_threshold,
            max_research_iterations=settings.max_research_iterations,
            max_budget_usd=settings.max_budget_usd,
            require_auth=settings.require_auth,
            export_formats=available_formats(),
            has_openai_key=bool(settings.openai_api_key),
            has_anthropic_key=bool(settings.anthropic_api_key),
            has_tavily_key=bool(settings.tavily_api_key),
            has_gemma_key=bool(settings.gemma_api_key or settings.google_api_key),
        )

    @app.post("/v1/research", response_model=CreateTaskResponse, dependencies=[auth_dep])
    async def create_task(body: CreateTaskRequest):
        state = await runtime_store.start(body.question, user_id=body.user_id)
        return CreateTaskResponse(
            task_id=state.task_id,
            stream_url=f"/v1/research/{state.task_id}/stream",
            snapshot=state.to_snapshot(),
        )

    @app.get("/v1/research", dependencies=[auth_dep])
    async def list_tasks():
        snapshots = await runtime_store.snapshots()
        return [snapshot.model_dump(mode="json") for snapshot in snapshots]

    @app.get("/v1/research/{task_id}", dependencies=[auth_dep])
    async def get_task(task_id: str):
        state = await runtime_store.get(task_id)
        if not state:
            raise HTTPException(404, "task not found")
        return state.to_snapshot().model_dump(mode="json")

    @app.post("/v1/research/{task_id}/interrupt", response_model=InterruptResponse, dependencies=[auth_dep])
    async def interrupt(task_id: str):
        return InterruptResponse(task_id=task_id, interrupted=runtime_store.interrupt(task_id))

    @app.post("/v1/research/{task_id}/pause", response_model=InterruptResponse, dependencies=[auth_dep])
    async def pause(task_id: str):
        """Alias for interrupt — kept for UI semantics. MVP does not separate
        pause from cancellation yet; future Postgres checkpointing will."""
        return InterruptResponse(task_id=task_id, interrupted=runtime_store.interrupt(task_id))

    @app.post("/v1/research/{task_id}/resume", dependencies=[auth_dep])
    async def resume(task_id: str):
        """MVP placeholder — once Postgres checkpointing lands the runtime can
        resume from the last persisted graph state. For now we return 409."""
        raise HTTPException(409, "resume is not yet supported (planned for v6 with PostgresSaver)")

    @app.post("/v1/research/{task_id}/review", dependencies=[auth_dep])
    async def submit_review(task_id: str, body: ReviewRequest):
        state = await runtime_store.get(task_id)
        if not state:
            raise HTTPException(404, "task not found")
        # Persist decision into metadata; runtime auto-approves in current MVP.
        state.metadata["review_decision"] = body.model_dump(mode="json")
        state.add_event("review_decision", node="api", decision=body.model_dump(mode="json"))
        await get_store().upsert_task(state)
        return {"task_id": task_id, "approved": body.approved}

    @app.get("/v1/research/{task_id}/events", dependencies=[auth_dep])
    async def recent_events(task_id: str):
        state = await runtime_store.get(task_id)
        if not state:
            raise HTTPException(404, "task not found")
        return [event.model_dump(mode="json") for event in state.events]

    @app.get("/v1/research/{task_id}/stream")
    async def stream(task_id: str, request: Request, after_seq: int = 0):
        # The web client uses fetch streaming so Authorization headers are available.
        await _verify_auth(request)
        state = await runtime_store.get(task_id)
        if not state:
            raise HTTPException(404, "task not found")

        async def gen():
            yield ":\n\n"  # initial comment to open the stream
            try:
                async for event in runtime_store.stream(task_id, replay=True, after_seq=after_seq):
                    if await request.is_disconnected():
                        break
                    yield "data: " + json.dumps(event.model_dump(mode="json"), ensure_ascii=False, default=str) + "\n\n"
                    if event.type in {"done", "error", "cancelled"}:
                        # Give the browser a moment to flush, then close.
                        await asyncio.sleep(0.05)
                        break
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("stream.error task_id=%s", task_id)
                yield "data: " + json.dumps({"type": "error", "error": str(exc)}) + "\n\n"
            yield "event: end\ndata: {}\n\n"

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.post("/v1/research/{task_id}/export", response_model=ExportResponse, dependencies=[auth_dep])
    async def export(task_id: str, fmt: str = "md"):
        state = await runtime_store.get(task_id)
        if not state:
            raise HTTPException(404, "task not found")
        if not state.final_report:
            raise HTTPException(409, "task has no final_report yet")
        try:
            path = get_exporter().export(state.final_report, fmt=fmt)
        except ExportError as exc:
            raise HTTPException(400, str(exc))
        size = path.stat().st_size
        return ExportResponse(
            task_id=task_id,
            format=fmt,
            filename=path.name,
            bytes=size,
            download_url=f"/v1/research/{task_id}/download?filename={path.name}",
        )

    @app.get("/v1/research/{task_id}/download")
    async def download(task_id: str, filename: str, request: Request):
        await _verify_auth(request)
        settings = get_settings()
        assert settings.export_dir is not None
        # Prevent path traversal: only accept files within the export directory and prefixed by the task id when possible.
        if "/" in filename or "\\" in filename or filename.startswith("."):
            raise HTTPException(400, "invalid filename")
        path = settings.export_dir / filename
        if not path.exists():
            raise HTTPException(404, "file not found")
        media = {
            ".md": "text/markdown; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(path.suffix.lower(), "application/octet-stream")
        return FileResponse(path, media_type=media, filename=path.name)

    @app.post("/v1/feedback", dependencies=[auth_dep])
    async def submit_feedback(body: FeedbackRequest):
        fb = Feedback(task_id=body.task_id, rating=body.rating, comment=body.comment)
        _memory_store.add_feedback(fb)
        return {"ok": True, "id": fb.id}

    @app.exception_handler(Exception)
    async def fallback_handler(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            raise exc
        logger.exception("api.unhandled path=%s", request.url.path)
        return JSONResponse({"detail": "internal error"}, status_code=500)

    return app


app = create_app()
