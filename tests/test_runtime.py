from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from athena.config import get_settings
from athena.graph.main_graph import run_research_graph_without_langgraph
from athena.runtime import runtime_store
from athena.state import ResearchState

TASK_QUESTION = "调研 Agent 框架企业落地"
TASK_TIMEOUT_SEC = 10


@pytest.fixture(autouse=True)
def _isolate_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ATHENA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ATHENA_REQUIRE_AUTH", "false")
    monkeypatch.setenv("ATHENA_ENV", "test")
    monkeypatch.setenv("ATHENA_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ATHENA_SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("ATHENA_MAX_RESEARCH_ITERATIONS", "1")
    monkeypatch.setenv("ATHENA_RATE_LIMIT_PER_MINUTE", "500")
    get_settings.cache_clear()
    _reset_runtime_singletons()
    yield
    _reset_runtime_singletons()
    get_settings.cache_clear()


def _reset_runtime_singletons() -> None:
    from athena.events import bus
    from athena.llm_factory import reset_llm_cache
    from athena.tools.search import reset_search_cache
    import athena.persistence.sqlite_store as sqlite_store

    runtime_store.states.clear()
    runtime_store.abort_flags.clear()
    runtime_store.tasks.clear()
    runtime_store.started = False
    bus._queues.clear()
    bus._replay.clear()
    bus._seq.clear()
    bus.persistence_hook = None
    reset_llm_cache()
    reset_search_cache()
    sqlite_store._store = None


@pytest.mark.asyncio
async def test_fallback_graph_generates_report():
    state = ResearchState(task_id="task_test", question=TASK_QUESTION)
    events = []
    async for event in run_research_graph_without_langgraph(state):
        events.append(event.type)
    assert state.final_report is not None
    assert state.quality is not None
    assert state.quality.overall >= 0.4
    assert "done" in events


def test_api_health_and_config():
    from athena.api.main import create_app

    with TestClient(create_app()) as client:
        health = client.get("/health").json()
        assert health["ok"] is True
        assert "version" in health
        cfg = client.get("/v1/config").json()
        assert cfg["llm_provider"] == "mock"
        assert "export_formats" in cfg


@pytest.mark.asyncio
async def test_api_create_and_export_task():
    import httpx
    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/v1/research",
                json={"question": TASK_QUESTION, "user_id": "u1"},
            )
            assert create_resp.status_code == 200
            task_id = create_resp.json()["task_id"]
            await asyncio.wait_for(runtime_store.tasks[task_id], timeout=TASK_TIMEOUT_SEC)
            state = await runtime_store.get(task_id)
            assert state is not None and state.final_report is not None
            export = (await client.post(f"/v1/research/{task_id}/export", params={"fmt": "md"})).json()
            assert export["filename"].endswith(".md")
            dl = await client.get(export["download_url"])
            assert dl.status_code == 200
            assert "#" in dl.text
