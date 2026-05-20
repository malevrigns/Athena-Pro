from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient


def _configure_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **overrides: str) -> None:
    values = {
        "ATHENA_DATA_DIR": str(tmp_path),
        "ATHENA_ENV": "test",
        "ATHENA_REQUIRE_AUTH": "false",
        "ATHENA_LLM_PROVIDER": "mock",
        "ATHENA_SEARCH_PROVIDER": "mock",
        "ATHENA_MAX_RESEARCH_ITERATIONS": "1",
        "ATHENA_RATE_LIMIT_PER_MINUTE": "500",
    }
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    from athena.config import get_settings
    from athena.tools.search import reset_search_cache
    import athena.persistence.sqlite_store as sqlite_store

    get_settings.cache_clear()
    reset_search_cache()
    sqlite_store._store = None


def test_dev_auth_requires_bearer_header_when_enabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _configure_env(
        monkeypatch,
        tmp_path,
        ATHENA_ENV="dev",
        ATHENA_REQUIRE_AUTH="true",
        ATHENA_API_KEY="secret-test-key",
    )

    from athena.api.main import create_app

    with TestClient(create_app()) as client:
        assert client.get("/v1/research").status_code == 401
        assert client.get("/v1/research?api_key=secret-test-key").status_code == 401
        assert client.get(
            "/v1/research",
            headers={"Authorization": "Bearer secret-test-key"},
        ).status_code == 200


def test_knowledge_csv_escapes_formula_cells(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/knowledge/items",
            json={
                "name": "=HYPERLINK(\"https://example.invalid\",\"x\")",
                "summary": "+SUM(1,1)",
                "source": "@remote",
                "tags": ["-tag"],
            },
        )
        assert response.status_code == 200

        csv_response = client.get("/v1/knowledge/items.csv")
        assert csv_response.status_code == 200
        body = csv_response.text
        assert "'=HYPERLINK" in body
        assert "'+SUM" in body
        assert "'@remote" in body
        assert "'-tag" in body


def test_knowledge_upload_rejects_oversized_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _configure_env(monkeypatch, tmp_path, ATHENA_MAX_UPLOAD_BYTES="16")

    from athena.api.main import create_app

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/knowledge/upload",
            files={"file": ("large.txt", b"x" * 17, "text/plain")},
        )

    assert response.status_code == 413


def test_verify_knowledge_item_updates_by_id_beyond_first_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    with TestClient(create_app()) as client:
        target = client.post("/v1/knowledge/items", json={"name": "old target"}).json()["id"]
        for index in range(100):
            response = client.post("/v1/knowledge/items", json={"name": f"new item {index}"})
            assert response.status_code == 200

        verified = client.post(f"/v1/knowledge/items/{target}/verify")

    assert verified.status_code == 200
    assert verified.json() == {"id": target, "status": "verified"}


def test_search_result_rejects_unsafe_url():
    from athena.tools.search import SearchResult

    with pytest.raises(ValueError, match="http"):
        SearchResult(title="bad", url="javascript:alert(1)", snippet="x").to_source()


def test_usage_event_is_recorded_before_terminal_done_event():
    from athena.schemas import TokenUsage
    from athena.state import ResearchState

    state = ResearchState(task_id="task_done", question="q")
    state.add_event("done", node="writer", final_report={"markdown": "# done"})
    state.add_usage(TokenUsage(model="mock-researcher", node="writer"))

    assert [event.type for event in state.events] == ["usage", "done"]


@pytest.mark.asyncio
async def test_mark_orphan_tasks_failed_updates_snapshot_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.persistence import get_store
    from athena.schemas import TaskStatus
    from athena.state import ResearchState

    store = get_store()
    state = ResearchState(task_id="task_orphan", question="q", status=TaskStatus.RESEARCHING)
    await store.upsert_task(state)

    count = await store.mark_orphan_tasks_failed()
    row = await store.fetch_task_json("task_orphan")

    assert count == 1
    assert row is not None
    assert row["status"] == "failed"
    assert json.loads(row["state_json"])["snapshot"]["status"] == "failed"
    await store.close()


@pytest.mark.asyncio
async def test_event_bus_filters_replay_by_sequence():
    from athena.events import EventBus
    from athena.schemas import StreamEvent

    event_bus = EventBus()
    await event_bus.publish(StreamEvent(type="status", task_id="task_seq", payload={"status": "planning"}))
    await event_bus.publish(StreamEvent(type="status", task_id="task_seq", payload={"status": "done"}))

    events: list[StreamEvent] = []
    async for event in event_bus.subscribe("task_seq", replay=True, after_seq=1):
        events.append(event)
        break

    assert events[0].seq == 2
    assert events[0].payload["status"] == "done"


@pytest.mark.asyncio
async def test_cost_tasks_csv_exports_real_usage_rows_and_escapes_cells(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app
    from athena.persistence import get_store
    from athena.schemas import StreamEvent
    from athena.state import ResearchState

    app = create_app()
    async with app.router.lifespan_context(app):
        store = get_store()
        state = ResearchState(task_id="task_cost_csv", question="=SUM(1,1)")
        await store.upsert_task(state)
        await store.append_event(
            StreamEvent(
                type="usage",
                task_id=state.task_id,
                payload={
                    "usage": {
                        "node": "writer",
                        "model": "mock-model",
                        "input_tokens": 123,
                        "output_tokens": 45,
                        "cost_usd": 0.0123,
                    }
                },
            ),
            1,
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/cost/tasks.csv", params={"range": "all"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "task_cost_csv" in response.text
    assert "writer" in response.text
    assert "mock-model" in response.text
    assert "'=SUM(1,1)" in response.text


@pytest.mark.asyncio
async def test_notifications_endpoint_reports_actionable_task_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app
    from athena.persistence import get_store
    from athena.schemas import TaskStatus
    from athena.state import ResearchState

    app = create_app()
    async with app.router.lifespan_context(app):
        store = get_store()
        await store.upsert_task(
            ResearchState(
                task_id="task_waiting_review",
                question="needs human approval",
                status=TaskStatus.WAITING_REVIEW,
            )
        )
        await store.upsert_task(
            ResearchState(
                task_id="task_failed",
                question="failed task",
                status=TaskStatus.FAILED,
            )
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/notifications")

    assert response.status_code == 200
    payload = response.json()
    assert payload["unread"] == 2
    routes = {item["route"] for item in payload["items"]}
    assert "/plan-review" in routes
    assert "/workbench/task_failed" in routes


@pytest.mark.asyncio
async def test_audit_endpoint_returns_real_review_and_citation_decisions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app
    from athena.persistence import get_store
    from athena.state import ResearchState

    app = create_app()
    async with app.router.lifespan_context(app):
        store = get_store()
        state = ResearchState(task_id="task_audit", question="audit trail question")
        state.metadata["review_decision"] = {
            "approved": False,
            "reviewer": "alice",
            "comments": "need more sources",
            "created_at": "2026-05-20T08:00:00+00:00",
        }
        await store.upsert_task(state)
        await store.upsert_citation_verification(
            "task_audit",
            2,
            "flag",
            "quote does not match",
            "bob",
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/audit/events", params={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    by_type = {item["type"]: item for item in payload["items"]}
    assert by_type["plan_review"]["status"] == "reject"
    assert by_type["plan_review"]["actor"] == "alice"
    assert by_type["plan_review"]["task_id"] == "task_audit"
    assert by_type["citation_verification"]["status"] == "flag"
    assert by_type["citation_verification"]["actor"] == "bob"


def test_researcher_includes_matching_knowledge_items(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)
    asyncio.run(_assert_researcher_includes_matching_knowledge_items())


async def _assert_researcher_includes_matching_knowledge_items():

    from athena.agents.researcher import Researcher
    from athena.persistence import get_store
    from athena.schemas import ResearchTopic
    from athena.tools.search import SearchClient

    class EmptySearchProvider:
        async def search(self, query: str, max_results: int = 5):
            return []

    store = get_store()
    try:
        await store.upsert_knowledge_item(
            {
                "id": "kn_sentinel",
                "name": "ACME_KNOWLEDGE_SENTINEL RAG cost playbook",
                "summary": "ACME_KNOWLEDGE_SENTINEL requires cache-first retrieval and per-tenant spend caps.",
                "type": "note",
                "source": "internal://playbook",
                "tags": ["rag", "cost"],
                "status": "verified",
            }
        )
        topic = ResearchTopic(
            title="RAG cost controls",
            question="How should ACME_KNOWLEDGE_SENTINEL guide RAG cost controls?",
            search_queries=["ACME_KNOWLEDGE_SENTINEL"],
        )

        finding = await Researcher(SearchClient(EmptySearchProvider())).run_topic(topic)

        assert any(source.source_type == "internal" for source in finding.sources)
        assert "ACME_KNOWLEDGE_SENTINEL" in "\n".join(finding.evidence)
    finally:
        await store.close()
