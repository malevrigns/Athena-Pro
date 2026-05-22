from __future__ import annotations

from pathlib import Path

import httpx
import pytest


def _configure_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ATHENA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ATHENA_ENV", "test")
    monkeypatch.setenv("ATHENA_REQUIRE_AUTH", "false")
    monkeypatch.setenv("ATHENA_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ATHENA_SEARCH_PROVIDER", "mock")

    from athena.config import get_settings
    import athena.persistence.sqlite_store as sqlite_store

    get_settings.cache_clear()
    sqlite_store._store = None


@pytest.mark.asyncio
async def test_project_api_create_list_get(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            create = await client.post(
                "/v1/projects",
                json={
                    "title": "RAG survey",
                    "research_question": "What baselines matter for RAG evaluation?",
                    "field": "NLP",
                    "constraints": ["single GPU"],
                },
            )
            assert create.status_code == 200
            project = create.json()
            assert project["title"] == "RAG survey"
            assert project["status"] == "draft"
            assert project["constraints"] == ["single GPU"]

            listed = await client.get("/v1/projects")
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()] == [project["id"]]

            fetched = await client.get(f"/v1/projects/{project['id']}")
            assert fetched.status_code == 200
            assert fetched.json()["research_question"] == project["research_question"]


@pytest.mark.asyncio
async def test_project_api_returns_404_for_missing_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/projects/proj_missing")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_project_paper_api_create_list_get_and_filter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            create_project = await client.post(
                "/v1/projects",
                json={"title": "RAG survey", "research_question": "What should we reproduce?"},
            )
            project = create_project.json()
            create_paper = await client.post(
                f"/v1/projects/{project['id']}/papers",
                json={
                    "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP",
                    "authors": ["Patrick Lewis"],
                    "year": 2020,
                    "venue": "NeurIPS",
                    "url": "https://example.com/rag-paper",
                    "code_url": "https://github.com/example/rag",
                    "dataset_mentions": ["Natural Questions"],
                    "screening_status": "included",
                    "relevance_score": 0.92,
                },
            )
            assert create_paper.status_code == 200
            paper = create_paper.json()
            assert paper["project_id"] == project["id"]
            assert paper["screening_status"] == "included"
            assert paper["dataset_mentions"] == ["Natural Questions"]

            listed = await client.get(f"/v1/projects/{project['id']}/papers")
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()] == [paper["id"]]

            filtered = await client.get(
                f"/v1/projects/{project['id']}/papers",
                params={"screening_status": "candidate"},
            )
            assert filtered.status_code == 200
            assert filtered.json() == []

            fetched = await client.get(f"/v1/projects/{project['id']}/papers/{paper['id']}")
            assert fetched.status_code == 200
            assert fetched.json()["title"] == paper["title"]


@pytest.mark.asyncio
async def test_project_paper_api_returns_404_for_wrong_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_a = (
                await client.post(
                    "/v1/projects",
                    json={"title": "A", "research_question": "What should A do?"},
                )
            ).json()
            project_b = (
                await client.post(
                    "/v1/projects",
                    json={"title": "B", "research_question": "What should B do?"},
                )
            ).json()
            paper = (
                await client.post(
                    f"/v1/projects/{project_a['id']}/papers",
                    json={"title": "owned by A"},
                )
            ).json()

            wrong_project = await client.get(f"/v1/projects/{project_b['id']}/papers/{paper['id']}")
            missing_project = await client.post(
                "/v1/projects/proj_missing/papers",
                json={"title": "missing"},
            )

    assert wrong_project.status_code == 404
    assert missing_project.status_code == 404


@pytest.mark.asyncio
async def test_project_paper_search_persists_papers_and_trace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project = (
                await client.post(
                    "/v1/projects",
                    json={"title": "Search", "research_question": "Which RAG baselines matter?"},
                )
            ).json()
            first = await client.post(
                f"/v1/projects/{project['id']}/paper-search",
                json={"query": "RAG baseline", "limit": 3},
            )
            assert first.status_code == 200
            first_payload = first.json()
            assert first_payload["ok"] is True
            assert first_payload["structured_output"]["created_count"] == 3

            second = await client.post(
                f"/v1/projects/{project['id']}/paper-search",
                json={"query": "RAG baseline", "limit": 3},
            )
            assert second.status_code == 200
            assert second.json()["structured_output"]["skipped_duplicates"] == 3

            papers = await client.get(f"/v1/projects/{project['id']}/papers")
            assert papers.status_code == 200
            assert len(papers.json()) == 3

            trace = await client.get(f"/v1/projects/{project['id']}/trace")
            assert trace.status_code == 200
            assert [item["call"]["tool_name"] for item in trace.json()] == [
                "paper_search",
                "paper_search",
            ]
            assert trace.json()[0]["observations"][0]["structured_output"]["created_count"] == 3


@pytest.mark.asyncio
async def test_project_paper_note_api_create_and_list(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project = (
                await client.post(
                    "/v1/projects",
                    json={"title": "Notes", "research_question": "How should notes work?"},
                )
            ).json()
            paper = (
                await client.post(
                    f"/v1/projects/{project['id']}/papers",
                    json={"title": "A note-worthy paper"},
                )
            ).json()
            created = await client.post(
                f"/v1/projects/{project['id']}/papers/{paper['id']}/notes",
                json={
                    "problem": "problem statement",
                    "method": "method summary",
                    "datasets": ["D1"],
                    "metrics": ["accuracy"],
                    "baselines": ["B1"],
                    "important_sections": ["3.1"],
                },
            )
            assert created.status_code == 200
            note = created.json()
            assert note["paper_id"] == paper["id"]
            assert note["datasets"] == ["D1"]

            listed = await client.get(f"/v1/projects/{project['id']}/papers/{paper['id']}/notes")
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()] == [note["id"]]


@pytest.mark.asyncio
async def test_project_paper_note_extract_persists_note_and_trace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project = (
                await client.post(
                    "/v1/projects",
                    json={"title": "Reader", "research_question": "Which baseline should we read?"},
                )
            ).json()
            paper = (
                await client.post(
                    f"/v1/projects/{project['id']}/papers",
                    json={
                        "title": "Retrieval-Augmented Generation",
                        "abstract": "RAG combines retrieval and generation.",
                        "code_url": "https://github.com/example/rag",
                        "dataset_mentions": ["Natural Questions"],
                    },
                )
            ).json()

            extracted = await client.post(
                f"/v1/projects/{project['id']}/papers/{paper['id']}/note-extract",
                json={},
            )
            assert extracted.status_code == 200
            payload = extracted.json()
            assert payload["ok"] is True
            assert payload["structured_output"]["paper_id"] == paper["id"]
            assert payload["structured_output"]["extraction_source"] == "fallback"
            assert payload["structured_output"]["prompt_word_count"] >= 5000
            assert payload["structured_output"]["note"]["datasets"] == ["Natural Questions"]

            notes = await client.get(f"/v1/projects/{project['id']}/papers/{paper['id']}/notes")
            assert notes.status_code == 200
            assert [note["id"] for note in notes.json()] == [payload["structured_output"]["note"]["id"]]

            trace = await client.get(f"/v1/projects/{project['id']}/trace")
            assert trace.status_code == 200
            assert trace.json()[-1]["call"]["tool_name"] == "paper_reader"


@pytest.mark.asyncio
async def test_project_paper_note_api_returns_404_for_wrong_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_a = (
                await client.post(
                    "/v1/projects",
                    json={"title": "A", "research_question": "What should A do?"},
                )
            ).json()
            project_b = (
                await client.post(
                    "/v1/projects",
                    json={"title": "B", "research_question": "What should B do?"},
                )
            ).json()
            paper = (
                await client.post(
                    f"/v1/projects/{project_a['id']}/papers",
                    json={"title": "owned by A"},
                )
            ).json()

            response = await client.post(
                f"/v1/projects/{project_b['id']}/papers/{paper['id']}/notes",
                json={"problem": "wrong project"},
            )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trace_api_returns_tool_calls_with_observations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app
    from athena.persistence import get_store
    from athena.research.tools import ToolCallRecord, ToolObservationRecord

    app = create_app()
    async with app.router.lifespan_context(app):
        repo = await get_store().research_repository()
        call = ToolCallRecord(task_id="task_trace", tool_name="paper_search", arguments={"query": "RAG"})
        await repo.record_tool_call(call)
        await repo.record_tool_observation(
            ToolObservationRecord(
                tool_call_id=call.id,
                summary="found 2 papers",
                structured_output={"count": 2},
            )
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/research/task_trace/trace")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["call"]["tool_name"] == "paper_search"
    assert payload[0]["observations"][0]["structured_output"] == {"count": 2}


@pytest.mark.asyncio
async def test_project_claim_extract_and_evidence_audit_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project = (
                await client.post(
                    "/v1/projects",
                    json={"title": "RAG", "research_question": "Which claims hold?"},
                )
            ).json()
            paper = (
                await client.post(
                    f"/v1/projects/{project['id']}/papers",
                    json={
                        "title": "Retrieval-Augmented Generation",
                        "abstract": "RAG combines retrieval and generation.",
                        "code_url": "https://github.com/example/rag",
                        "dataset_mentions": ["Natural Questions"],
                    },
                )
            ).json()

            extracted = await client.post(
                f"/v1/projects/{project['id']}/papers/{paper['id']}/claim-extract",
                json={},
            )
            assert extracted.status_code == 200
            payload = extracted.json()
            assert payload["ok"] is True
            assert payload["structured_output"]["claim_count"] >= 2

            claims = await client.get(f"/v1/projects/{project['id']}/claims")
            assert claims.status_code == 200
            assert len(claims.json()) == payload["structured_output"]["claim_count"]

            evidence = await client.get(f"/v1/projects/{project['id']}/evidence")
            assert evidence.status_code == 200
            assert len(evidence.json()) == payload["structured_output"]["evidence_count"]

            audit = await client.post(f"/v1/projects/{project['id']}/evidence/audit")
            assert audit.status_code == 200
            report = audit.json()
            assert report["total_claims"] == len(claims.json())
            assert report["unsupported_claims"] == 0
            assert report["completeness_ratio"] == 1.0

            # claim extraction is recorded on the project trace.
            trace = await client.get(f"/v1/projects/{project['id']}/trace")
            assert trace.json()[-1]["call"]["tool_name"] == "claim_extract"


@pytest.mark.asyncio
async def test_project_paper_matrix_json_and_csv_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project = (
                await client.post(
                    "/v1/projects",
                    json={"title": "RAG", "research_question": "What to compare?"},
                )
            ).json()
            await client.post(
                f"/v1/projects/{project['id']}/papers",
                json={
                    "title": "Retrieval-Augmented Generation",
                    "year": 2020,
                    "code_url": "https://github.com/example/rag",
                },
            )

            matrix = await client.get(f"/v1/projects/{project['id']}/paper-matrix")
            assert matrix.status_code == 200
            body = matrix.json()
            assert body["row_count"] == 1
            assert body["rows"][0]["title"] == "Retrieval-Augmented Generation"

            csv_export = await client.get(f"/v1/projects/{project['id']}/paper-matrix.csv")
            assert csv_export.status_code == 200
            assert csv_export.headers["content-type"].startswith("text/csv")
            assert csv_export.text.splitlines()[0].startswith("paper_id,title,year")


@pytest.mark.asyncio
async def test_project_citation_graph_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project = (
                await client.post(
                    "/v1/projects",
                    json={"title": "RAG", "research_question": "How are papers related?"},
                )
            ).json()
            for title in ("Retrieval Augmented Generation", "Retrieval Augmented Generation v2"):
                await client.post(
                    f"/v1/projects/{project['id']}/papers",
                    json={"title": title, "dataset_mentions": ["Natural Questions"]},
                )

            response = await client.post(
                f"/v1/projects/{project['id']}/citation-graph",
                json={},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["ok"] is True
            assert payload["structured_output"]["node_count"] == 2
            assert payload["structured_output"]["edge_count"] == 1


@pytest.mark.asyncio
async def test_project_trace_api_returns_project_scoped_trace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app
    from athena.persistence import get_store
    from athena.research.domain import ResearchProject
    from athena.research.tools import ToolCallRecord, ToolObservationRecord

    app = create_app()
    async with app.router.lifespan_context(app):
        repo = await get_store().research_repository()
        project = ResearchProject(title="RAG", research_question="What should we reproduce?")
        await repo.create_project(project)
        call = ToolCallRecord(
            task_id="task_trace",
            project_id=project.id,
            tool_name="paper_search",
            arguments={"query": "RAG"},
        )
        await repo.record_tool_call(call)
        await repo.record_tool_observation(
            ToolObservationRecord(tool_call_id=call.id, summary="found papers")
        )
        await repo.record_tool_call(
            ToolCallRecord(task_id="task_other", project_id="proj_other", tool_name="ignored")
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/v1/projects/{project.id}/trace")

    assert response.status_code == 200
    payload = response.json()
    assert [item["call"]["tool_name"] for item in payload] == ["paper_search"]
    assert payload[0]["observations"][0]["summary"] == "found papers"


@pytest.mark.asyncio
async def test_review_endpoints_list_get_and_approve(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app
    from athena.persistence import get_store
    from athena.research.domain import CheckpointType
    from athena.research.runtime import CheckpointService

    app = create_app()
    async with app.router.lifespan_context(app):
        repo = await get_store().research_repository()
        from athena.research.domain import ResearchProject

        project = ResearchProject(title="RAG", research_question="Approve what?")
        await repo.create_project(project)
        checkpoint = await CheckpointService(repo).open(
            task_id="task_1",
            project_id=project.id,
            checkpoint_type=CheckpointType.plan_review,
            title="Approve the plan",
            content={"steps": ["search", "read"]},
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            listed = await client.get(f"/v1/projects/{project.id}/reviews")
            assert listed.status_code == 200
            assert [r["id"] for r in listed.json()] == [checkpoint.id]
            assert listed.json()[0]["status"] == "pending"

            fetched = await client.get(f"/v1/research/reviews/{checkpoint.id}")
            assert fetched.status_code == 200
            assert fetched.json()["title"] == "Approve the plan"

            approved = await client.post(
                f"/v1/research/reviews/{checkpoint.id}/approve",
                json={"comment": "looks good"},
            )
            assert approved.status_code == 200
            assert approved.json()["status"] == "decided"
            assert approved.json()["decision"] == "approved"
            assert approved.json()["comment"] == "looks good"

            missing = await client.get("/v1/research/reviews/ckpt_missing")
            assert missing.status_code == 404
            bad_reject = await client.post("/v1/research/reviews/ckpt_missing/reject", json={})
            assert bad_reject.status_code == 404


@pytest.mark.asyncio
async def test_review_api_wakes_a_session_blocked_on_plan_review(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """The decisive integration test: a POST decision unblocks a live run."""
    _configure_env(monkeypatch, tmp_path)

    import asyncio

    from athena.api.main import create_app
    from athena.persistence import get_store
    from athena.research.domain import ResearchProject
    from athena.research.runtime import AgentStep, ResearchSession, ScriptedBrain
    from athena.research.tools import PermissionLevel, ToolResult, ToolRouter, ToolSpec

    async def _handler(arguments: dict) -> ToolResult:
        return ToolResult(ok=True, summary="ok")

    app = create_app()
    async with app.router.lifespan_context(app):
        repo = await get_store().research_repository()
        project = ResearchProject(title="RAG", research_question="Run me?")
        await repo.create_project(project)
        router = ToolRouter(
            [
                ToolSpec(
                    name="paper_search",
                    description="search",
                    parameters_schema={"type": "object"},
                    handler=_handler,
                    permission_level=PermissionLevel.network_read,
                )
            ]
        )
        session = ResearchSession(repository=repo, router=router, project=project)
        brain = ScriptedBrain(steps=[AgentStep(kind="final", final_answer="done")])

        run_task = asyncio.create_task(
            session.run(brain=brain, goal="survey", plan={"steps": ["x"]}, require_plan_review=True)
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            checkpoint_id = None
            for _ in range(200):
                reviews = (await client.get(f"/v1/projects/{project.id}/reviews")).json()
                pending = [r for r in reviews if r["status"] == "pending"]
                if pending:
                    checkpoint_id = pending[0]["id"]
                    break
                await asyncio.sleep(0.01)
            assert checkpoint_id is not None, "session never opened a plan-review checkpoint"
            assert not run_task.done()  # the run is genuinely blocked

            approved = await client.post(
                f"/v1/research/reviews/{checkpoint_id}/approve", json={}
            )
            assert approved.status_code == 200

        result = await asyncio.wait_for(run_task, timeout=3)
        assert result.started is True
        assert result.plan_review.decision == "approved"
        assert result.loop_result is not None


@pytest.mark.asyncio
async def test_phase5_taxonomy_baseline_and_idea_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project = (
                await client.post(
                    "/v1/projects",
                    json={"title": "RAG", "research_question": "Which baseline to reproduce?"},
                )
            ).json()
            paper = (
                await client.post(
                    f"/v1/projects/{project['id']}/papers",
                    json={"title": "RAG", "code_url": "https://github.com/example/rag"},
                )
            ).json()
            await client.post(
                f"/v1/projects/{project['id']}/papers/{paper['id']}/notes",
                json={"method": "retriever + generator", "datasets": ["NQ"], "metrics": ["EM"]},
            )

            built = await client.post(f"/v1/projects/{project['id']}/taxonomy/build", json={})
            assert built.status_code == 200 and built.json()["ok"] is True
            taxonomy = await client.get(f"/v1/projects/{project['id']}/taxonomy")
            assert taxonomy.status_code == 200
            assert taxonomy.json()["nodes"]

            extracted = await client.post(f"/v1/projects/{project['id']}/baselines/extract", json={})
            assert extracted.json()["structured_output"]["created_count"] == 1
            ranked = await client.post(
                f"/v1/projects/{project['id']}/baselines/rank", json={"goal": "RAG"}
            )
            assert ranked.json()["ok"] is True
            baselines = await client.get(f"/v1/projects/{project['id']}/baselines")
            assert baselines.json()[0]["rank_score"] is not None

            idea = await client.post(
                f"/v1/projects/{project['id']}/ideas",
                json={
                    "title": "adaptive retrieval depth",
                    "motivation": "latency",
                    "core_hypothesis": "depth can be learned",
                    "method_sketch": "a controller predicts depth",
                    "novelty_score": 0.8,
                    "risk_score": 0.3,
                },
            )
            assert idea.status_code == 200
            idea_rank = await client.post(f"/v1/projects/{project['id']}/ideas/rank", json={})
            assert idea_rank.json()["ok"] is True
            ideas = await client.get(f"/v1/projects/{project['id']}/ideas")
            assert ideas.json()[0]["overall_score"] is not None


@pytest.mark.asyncio
async def test_taxonomy_endpoint_404_before_any_build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _configure_env(monkeypatch, tmp_path)

    from athena.api.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project = (
                await client.post(
                    "/v1/projects",
                    json={"title": "RAG", "research_question": "Untouched project?"},
                )
            ).json()
            response = await client.get(f"/v1/projects/{project['id']}/taxonomy")
    assert response.status_code == 404
