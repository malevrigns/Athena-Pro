from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from athena.config import get_settings
from athena.api.main import app
from athena.graph.main_graph import run_research_graph_without_langgraph
from athena.runtime import runtime_store
from athena.state import ResearchState


@pytest.fixture(autouse=True)
def _isolate_data(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ATHENA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ATHENA_REQUIRE_AUTH", "false")
    monkeypatch.setenv("ATHENA_ENV", "dev")
    monkeypatch.setenv("ATHENA_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ATHENA_SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("ATHENA_MAX_RESEARCH_ITERATIONS", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_fallback_graph_generates_report():
    state = ResearchState(task_id="task_test", question="调研 Agent 框架企业落地")
    events = []
    async for event in run_research_graph_without_langgraph(state):
        events.append(event.type)
    assert state.final_report is not None
    assert state.quality is not None
    assert state.quality.overall >= 0.4
    assert "done" in events


def test_api_health_and_config():
    client = TestClient(app)
    health = client.get("/health").json()
    assert health["ok"] is True
    assert "version" in health
    cfg = client.get("/v1/config").json()
    assert cfg["llm_provider"] == "mock"
    assert "export_formats" in cfg


@pytest.mark.asyncio
async def test_api_create_and_export_task():
    import httpx
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/v1/research", json={"question": "调研 Agent 框架企业落地", "user_id": "u1"})
        assert create_resp.status_code == 200
        task_id = create_resp.json()["task_id"]
        for _ in range(80):
            state = await runtime_store.get(task_id)
            if state and state.final_report is not None:
                break
            await asyncio.sleep(0.05)
        assert state is not None and state.final_report is not None
        export = (await client.post(f"/v1/research/{task_id}/export", params={"fmt": "md"})).json()
        assert export["filename"].endswith(".md")
        dl = await client.get(export["download_url"])
        assert dl.status_code == 200
        assert "#" in dl.text  # markdown body
