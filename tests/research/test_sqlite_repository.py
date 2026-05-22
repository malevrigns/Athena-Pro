"""SQLite persistence tests for Research OS (Phase 1, step 2).

Covers schema creation/idempotency, ResearchProject round-trips, ordering,
and that existing legacy task/event persistence is unaffected.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from athena.persistence.sqlite_store import SQLiteStore
from athena.research.domain import Paper, PaperNote, PaperScreeningStatus, ProjectStatus, ResearchProject
from athena.research.persistence import RESEARCH_OS_SCHEMA
from athena.research.tools import (
    PermissionLevel,
    ToolCallRecord,
    ToolCallStatus,
    ToolObservationRecord,
    ToolObservationStatus,
)

RESEARCH_OS_TABLES = [
    "research_projects",
    "papers",
    "paper_notes",
    "claims",
    "evidence",
    "method_taxonomies",
    "baseline_candidates",
    "research_ideas",
    "experiment_specs",
    "experiment_runs",
    "code_artifacts",
    "tool_calls",
    "tool_observations",
    "review_checkpoints",
    "research_events",
]

LEGACY_TABLES = [
    "tasks",
    "events",
    "citation_verifications",
    "app_settings",
    "knowledge_collections",
    "knowledge_items",
]


@pytest.fixture
def make_store(tmp_path, monkeypatch):
    """Yield a factory for isolated SQLiteStores; close them all on teardown."""
    for key, value in {
        "ATHENA_DATA_DIR": str(tmp_path),
        "ATHENA_ENV": "test",
        "ATHENA_REQUIRE_AUTH": "false",
        "ATHENA_LLM_PROVIDER": "mock",
        "ATHENA_SEARCH_PROVIDER": "mock",
    }.items():
        monkeypatch.setenv(key, value)

    from athena.config import get_settings

    get_settings.cache_clear()
    stores: list[SQLiteStore] = []

    def _make(name: str = "research_os.db") -> SQLiteStore:
        store = SQLiteStore(tmp_path / name)
        stores.append(store)
        return store

    yield _make

    async def _close_all() -> None:
        for store in stores:
            await store.close()

    asyncio.run(_close_all())
    get_settings.cache_clear()


async def _table_names(store: SQLiteStore) -> set[str]:
    assert store._conn is not None
    cursor = await store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )
    rows = await cursor.fetchall()
    await cursor.close()
    return {row[0] for row in rows}


@pytest.mark.asyncio
async def test_schema_creates_all_research_os_tables(make_store):
    store = make_store()
    await store.connect()
    tables = await _table_names(store)
    for name in RESEARCH_OS_TABLES:
        assert name in tables, f"missing Research OS table: {name}"


@pytest.mark.asyncio
async def test_legacy_tables_still_exist_after_initialization(make_store):
    store = make_store()
    await store.connect()
    tables = await _table_names(store)
    for name in LEGACY_TABLES:
        assert name in tables, f"missing legacy table: {name}"


@pytest.mark.asyncio
async def test_schema_initialization_is_idempotent(make_store):
    # First store creates the schema and seeds a project.
    store1 = make_store()
    repo1 = await store1.research_repository()
    project = ResearchProject(title="P", research_question="Q?")
    await repo1.create_project(project)
    await store1.close()

    # Re-opening the same database file must not error and must keep data.
    store2 = make_store()  # same tmp_path + default name -> same file
    await store2.connect()
    tables = await _table_names(store2)
    for name in RESEARCH_OS_TABLES:
        assert name in tables
    repo2 = await store2.research_repository()
    assert await repo2.get_project(project.id) is not None

    # Re-running the schema script directly is also a harmless no-op.
    assert store2._conn is not None
    await store2._conn.executescript(RESEARCH_OS_SCHEMA)
    await store2._conn.commit()
    assert await repo2.get_project(project.id) is not None


@pytest.mark.asyncio
async def test_create_and_get_project_round_trips(make_store):
    store = make_store()
    repo = await store.research_repository()
    project = ResearchProject(
        title="LLM evaluation methods",
        field="NLP",
        research_question="How to evaluate LLM reasoning?",
        constraints=["single GPU", "deadline 2026-09"],
        target_venue="NeurIPS",
        status=ProjectStatus.planning,
        owner="researcher-1",
    )
    await repo.create_project(project)
    restored = await repo.get_project(project.id)
    assert restored == project


@pytest.mark.asyncio
async def test_get_missing_project_returns_none(make_store):
    store = make_store()
    repo = await store.research_repository()
    assert await repo.get_project("proj_does_not_exist") is None


@pytest.mark.asyncio
async def test_constraints_list_round_trips(make_store):
    store = make_store()
    repo = await store.research_repository()

    with_constraints = ResearchProject(
        title="A", research_question="Q?", constraints=["c1", "c2", "c3"]
    )
    await repo.create_project(with_constraints)
    restored = await repo.get_project(with_constraints.id)
    assert restored.constraints == ["c1", "c2", "c3"]

    empty = ResearchProject(title="B", research_question="Q?")
    await repo.create_project(empty)
    restored_empty = await repo.get_project(empty.id)
    assert restored_empty.constraints == []
    # default collections must stay isolated across persisted instances
    assert restored_empty.constraints is not restored.constraints


@pytest.mark.asyncio
async def test_enum_status_round_trips(make_store):
    store = make_store()
    repo = await store.research_repository()
    for status in ProjectStatus:
        project = ResearchProject(
            title="S", research_question="Q?", status=status
        )
        await repo.create_project(project)
        restored = await repo.get_project(project.id)
        assert restored.status is status
        assert isinstance(restored.status, ProjectStatus)


@pytest.mark.asyncio
async def test_default_owner_round_trips_as_none(make_store):
    store = make_store()
    repo = await store.research_repository()
    project = ResearchProject(title="no owner", research_question="Q?")
    await repo.create_project(project)
    restored = await repo.get_project(project.id)
    assert restored.owner is None


@pytest.mark.asyncio
async def test_list_projects_orders_by_updated_at_desc(make_store):
    store = make_store()
    repo = await store.research_repository()
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    # insert in deliberately unsorted order
    await repo.create_project(
        ResearchProject(
            title="middle", research_question="Q?",
            created_at=base, updated_at=base + timedelta(hours=1),
        )
    )
    await repo.create_project(
        ResearchProject(
            title="newest", research_question="Q?",
            created_at=base, updated_at=base + timedelta(hours=2),
        )
    )
    await repo.create_project(
        ResearchProject(
            title="oldest", research_question="Q?",
            created_at=base, updated_at=base,
        )
    )
    listed = await repo.list_projects()
    assert [p.title for p in listed] == ["newest", "middle", "oldest"]


@pytest.mark.asyncio
async def test_list_projects_respects_limit(make_store):
    store = make_store()
    repo = await store.research_repository()
    for i in range(5):
        await repo.create_project(
            ResearchProject(title=f"p{i}", research_question="Q?")
        )
    assert len(await repo.list_projects(limit=3)) == 3


@pytest.mark.asyncio
async def test_upsert_project_updates_existing_row_in_place(make_store):
    store = make_store()
    repo = await store.research_repository()
    project = ResearchProject(title="draft title", research_question="Q?")
    await repo.create_project(project)

    updated = project.model_copy(
        update={
            "title": "final title",
            "status": ProjectStatus.completed,
            "updated_at": project.updated_at + timedelta(hours=1),
        }
    )
    await repo.upsert_project(updated)

    restored = await repo.get_project(project.id)
    assert restored.title == "final title"
    assert restored.status is ProjectStatus.completed
    assert len(await repo.list_projects()) == 1  # upserted, not duplicated


@pytest.mark.asyncio
async def test_create_and_list_project_papers_round_trip(make_store):
    store = make_store()
    repo = await store.research_repository()
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    project = ResearchProject(title="literature", research_question="Q?")
    await repo.create_project(project)
    older = Paper(
        project_id=project.id,
        title="older paper",
        authors=["A", "B"],
        year=2024,
        venue="ICLR",
        abstract="older abstract",
        url="https://example.com/older",
        code_url="https://github.com/example/older",
        dataset_mentions=["MMLU"],
        screening_status=PaperScreeningStatus.included,
        relevance_score=0.71,
        created_at=base,
    )
    newer = Paper(
        project_id=project.id,
        title="newer paper",
        authors=["C"],
        year=2025,
        venue="NeurIPS",
        doi="10.0000/example",
        semantic_scholar_id="ss_1",
        citation_count=42,
        screening_status=PaperScreeningStatus.candidate,
        relevance_score=0.91,
        created_at=base + timedelta(minutes=1),
    )

    await repo.create_paper(older)
    await repo.create_paper(newer)

    assert await repo.get_paper(older.id) == older
    assert await repo.get_paper("paper_missing") is None
    assert [paper.title for paper in await repo.list_project_papers(project.id)] == [
        "newer paper",
        "older paper",
    ]


@pytest.mark.asyncio
async def test_project_papers_are_scoped_filterable_and_upsertable(make_store):
    store = make_store()
    repo = await store.research_repository()
    project_a = ResearchProject(title="A", research_question="Q?")
    project_b = ResearchProject(title="B", research_question="Q?")
    await repo.create_project(project_a)
    await repo.create_project(project_b)
    included = Paper(
        project_id=project_a.id,
        title="included",
        screening_status=PaperScreeningStatus.included,
    )
    excluded = Paper(
        project_id=project_a.id,
        title="excluded",
        screening_status=PaperScreeningStatus.excluded,
    )
    other_project = Paper(project_id=project_b.id, title="other")

    await repo.create_paper(included)
    await repo.create_paper(excluded)
    await repo.create_paper(other_project)
    updated = included.model_copy(
        update={
            "title": "included updated",
            "screening_status": PaperScreeningStatus.read,
        }
    )
    await repo.upsert_paper(updated)

    assert [paper.title for paper in await repo.list_project_papers(project_a.id)] == [
        "excluded",
        "included updated",
    ]
    assert [paper.title for paper in await repo.list_project_papers(project_b.id)] == ["other"]
    read = await repo.list_project_papers(
        project_a.id,
        screening_status=PaperScreeningStatus.read,
    )
    assert read == [updated]


@pytest.mark.asyncio
async def test_create_and_list_paper_notes_round_trip(make_store):
    store = make_store()
    repo = await store.research_repository()
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    project = ResearchProject(title="notes", research_question="Q?")
    await repo.create_project(project)
    paper = Paper(project_id=project.id, title="paper")
    await repo.create_paper(paper)
    older = PaperNote(
        paper_id=paper.id,
        problem="problem",
        method="method",
        training_setup="training",
        datasets=["D1"],
        metrics=["accuracy"],
        baselines=["B1"],
        main_results="results",
        limitations="limits",
        reproducibility_notes="repro notes",
        important_sections=["3.1"],
        created_at=base,
    )
    newer = PaperNote(
        paper_id=paper.id,
        problem="new problem",
        created_at=base + timedelta(minutes=1),
    )

    await repo.create_paper_note(older)
    await repo.create_paper_note(newer)

    assert await repo.get_paper_note(older.id) == older
    assert await repo.get_paper_note("note_missing") is None
    assert [note.id for note in await repo.list_paper_notes(paper.id)] == [newer.id, older.id]


@pytest.mark.asyncio
async def test_upsert_paper_note_updates_existing_row(make_store):
    store = make_store()
    repo = await store.research_repository()
    project = ResearchProject(title="notes", research_question="Q?")
    await repo.create_project(project)
    paper = Paper(project_id=project.id, title="paper")
    await repo.create_paper(paper)
    note = PaperNote(paper_id=paper.id, problem="old", datasets=["D1"])
    await repo.create_paper_note(note)

    updated = note.model_copy(
        update={
            "problem": "new",
            "method": "better method",
            "datasets": ["D2", "D3"],
        }
    )
    await repo.upsert_paper_note(updated)

    assert await repo.get_paper_note(note.id) == updated
    assert len(await repo.list_paper_notes(paper.id)) == 1


@pytest.mark.asyncio
async def test_existing_task_persistence_still_works(make_store):
    """Legacy task/event persistence must be unchanged by Research OS tables."""
    from athena.schemas import StreamEvent
    from athena.state import ResearchState

    store = make_store()
    state = ResearchState(task_id="task_persist", question="legacy task still works")
    await store.upsert_task(state)
    await store.append_event(
        StreamEvent(type="status", task_id="task_persist", payload={"status": "planning"}),
        1,
    )

    row = await store.fetch_task_json("task_persist")
    assert row is not None
    assert row["task_id"] == "task_persist"
    assert row["question"] == "legacy task still works"

    events = await store.fetch_events("task_persist")
    assert [event.type for event in events] == ["status"]

    # Research OS persistence coexists on the same connection.
    repo = await store.research_repository()
    await repo.create_project(
        ResearchProject(title="coexist", research_question="Q?")
    )
    assert len(await repo.list_projects()) == 1


@pytest.mark.asyncio
async def test_tool_call_and_observation_round_trip(make_store):
    store = make_store()
    repo = await store.research_repository()
    call = ToolCallRecord(
        task_id="task_trace",
        project_id="proj_trace",
        tool_name="paper_search",
        arguments={"query": "RAG", "limit": 5},
        permission_level=PermissionLevel.network_read,
        status=ToolCallStatus.completed,
    )
    observation = ToolObservationRecord(
        tool_call_id=call.id,
        status=ToolObservationStatus.ok,
        summary="found papers",
        structured_output={"count": 3, "titles": ["a", "b", "c"]},
    )

    await repo.record_tool_call(call)
    await repo.record_tool_observation(observation)

    calls = await repo.list_tool_calls("task_trace")
    project_calls = await repo.list_project_tool_calls("proj_trace")
    observations = await repo.list_tool_observations(call.id)

    assert calls == [call]
    assert project_calls == [call]
    assert observations == [observation]


@pytest.mark.asyncio
async def test_tool_trace_orders_by_created_at(make_store):
    store = make_store()
    repo = await store.research_repository()
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    newest = ToolCallRecord(
        task_id="task_order",
        tool_name="new",
        created_at=base + timedelta(minutes=1),
    )
    oldest = ToolCallRecord(
        task_id="task_order",
        tool_name="old",
        created_at=base,
    )

    await repo.record_tool_call(newest)
    await repo.record_tool_call(oldest)

    assert [call.tool_name for call in await repo.list_tool_calls("task_order")] == ["old", "new"]


@pytest.mark.asyncio
async def test_project_tool_trace_orders_by_created_at(make_store):
    store = make_store()
    repo = await store.research_repository()
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    first = ToolCallRecord(
        task_id="task_a",
        project_id="proj_order",
        tool_name="first",
        created_at=base,
    )
    second = ToolCallRecord(
        task_id="task_b",
        project_id="proj_order",
        tool_name="second",
        created_at=base + timedelta(minutes=1),
    )
    other = ToolCallRecord(
        task_id="task_c",
        project_id="proj_other",
        tool_name="other",
        created_at=base + timedelta(minutes=2),
    )

    await repo.record_tool_call(second)
    await repo.record_tool_call(other)
    await repo.record_tool_call(first)

    assert [call.tool_name for call in await repo.list_project_tool_calls("proj_order")] == [
        "first",
        "second",
    ]


@pytest.mark.asyncio
async def test_tool_observations_can_be_loaded_in_batch(make_store):
    store = make_store()
    repo = await store.research_repository()
    first = ToolCallRecord(task_id="task_batch", tool_name="first")
    second = ToolCallRecord(task_id="task_batch", tool_name="second")
    await repo.record_tool_call(first)
    await repo.record_tool_call(second)
    await repo.record_tool_observation(
        ToolObservationRecord(tool_call_id=first.id, summary="first observation")
    )
    await repo.record_tool_observation(
        ToolObservationRecord(tool_call_id=second.id, summary="second observation")
    )

    grouped = await repo.list_tool_observations_for_calls([first.id, second.id, "missing"])

    assert [obs.summary for obs in grouped[first.id]] == ["first observation"]
    assert [obs.summary for obs in grouped[second.id]] == ["second observation"]
    assert grouped["missing"] == []


@pytest.mark.asyncio
async def test_list_projects_orders_correctly_across_timezone_offsets(make_store):
    """updated_at is normalized to UTC before storage, so list_projects orders
    by the real instant regardless of the offset each project carried."""
    store = make_store()
    repo = await store.research_repository()

    tokyo = timezone(timedelta(hours=9))      # 12:00 here == 03:00 UTC (earliest)
    new_york = timezone(timedelta(hours=-5))  # 12:00 here == 17:00 UTC (latest)
    wall = dict(year=2026, month=5, day=1, hour=12)

    earliest = ResearchProject(
        title="tokyo-noon", research_question="Q?",
        updated_at=datetime(**wall, tzinfo=tokyo),
    )
    middle = ResearchProject(
        title="utc-noon", research_question="Q?",
        updated_at=datetime(**wall, tzinfo=timezone.utc),
    )
    latest = ResearchProject(
        title="new-york-noon", research_question="Q?",
        updated_at=datetime(**wall, tzinfo=new_york),
    )
    # insert in deliberately unsorted order
    await repo.create_project(middle)
    await repo.create_project(latest)
    await repo.create_project(earliest)

    listed = await repo.list_projects()
    assert [p.title for p in listed] == ["new-york-noon", "utc-noon", "tokyo-noon"]
    # the normalized instant survives the round-trip
    assert listed[0].updated_at == latest.updated_at


@pytest.mark.asyncio
async def test_naive_datetime_is_stored_and_returned_as_utc(make_store):
    """Naive datetimes are treated as UTC, not silently offset-shifted."""
    store = make_store()
    repo = await store.research_repository()
    naive = datetime(2026, 5, 1, 8, 30)  # no tzinfo
    project = ResearchProject(
        title="naive-dt", research_question="Q?",
        created_at=naive, updated_at=naive,
    )
    await repo.create_project(project)
    restored = await repo.get_project(project.id)
    assert restored.updated_at == datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
    assert restored.created_at.tzinfo is not None


@pytest.mark.asyncio
async def test_claim_and_evidence_round_trip_and_project_scope(make_store):
    from athena.research.domain import Claim, ClaimType, Evidence

    store = make_store()
    repo = await store.research_repository()
    project = ResearchProject(title="claims", research_question="Q?")
    other = ResearchProject(title="other", research_question="Q?")
    await repo.create_project(project)
    await repo.create_project(other)

    claim = Claim(
        project_id=project.id,
        text="The method improves accuracy by 3 points.",
        claim_type=ClaimType.result,
        paper_id="paper_1",
        section="result",
        confidence=0.8,
    )
    evidence = Evidence(
        claim_id=claim.id,
        source_type="paper_note",
        paper_id="paper_1",
        section="result",
        quote="we observe a 3 point gain on MMLU",
        verification_status="verified",
    )
    claim.evidence_ids = [evidence.id]
    await repo.create_claim(claim)
    await repo.create_evidence(evidence)
    # a claim on a different project must not leak into project scope
    await repo.create_claim(
        Claim(project_id=other.id, text="other", claim_type=ClaimType.method)
    )

    assert await repo.get_claim(claim.id) == claim
    assert await repo.list_project_claims(project.id) == [claim]
    assert await repo.list_paper_claims("paper_1") == [claim]
    assert await repo.get_evidence(evidence.id) == evidence
    assert await repo.list_claim_evidence(claim.id) == [evidence]
    assert await repo.list_project_evidence(project.id) == [evidence]
    assert await repo.list_project_evidence(other.id) == []


@pytest.mark.asyncio
async def test_review_checkpoint_round_trip_and_decision_update(make_store):
    from athena.research.domain import (
        CheckpointStatus,
        CheckpointType,
        ResearchProject,
        ReviewCheckpoint,
        ReviewDecision,
    )

    store = make_store()
    repo = await store.research_repository()
    project = ResearchProject(title="ckpt", research_question="Q?")
    await repo.create_project(project)
    checkpoint = ReviewCheckpoint(
        task_id="task_1",
        project_id=project.id,
        checkpoint_type=CheckpointType.plan_review,
        title="Approve the research plan",
        content={"steps": ["search", "read", "synthesize"]},
    )
    await repo.create_checkpoint(checkpoint)

    restored = await repo.get_checkpoint(checkpoint.id)
    assert restored == checkpoint
    assert restored.status is CheckpointStatus.pending
    assert restored.decision is None

    decided = checkpoint.model_copy(
        update={
            "status": CheckpointStatus.decided,
            "decision": ReviewDecision.approved,
            "comment": "looks good",
            "decided_at": checkpoint.created_at + timedelta(minutes=5),
        }
    )
    await repo.upsert_checkpoint(decided)
    reloaded = await repo.get_checkpoint(checkpoint.id)
    assert reloaded.status is CheckpointStatus.decided
    assert reloaded.decision is ReviewDecision.approved
    assert reloaded.comment == "looks good"
    assert [c.id for c in await repo.list_project_checkpoints(project.id)] == [checkpoint.id]


@pytest.mark.asyncio
async def test_research_event_log_round_trips_and_orders_by_seq(make_store):
    from athena.research.events import RESEARCH_EVENT_ADAPTER, StatusEvent, ToolCallEvent

    store = make_store()
    repo = await store.research_repository()
    second = ToolCallEvent(
        task_id="task_evt",
        project_id="proj_evt",
        seq=2,
        payload={
            "tool_call_id": "tc_1",
            "tool_name": "paper_search",
            "arguments": {"query": "RAG"},
        },
    )
    first = StatusEvent(
        task_id="task_evt",
        project_id="proj_evt",
        seq=1,
        payload={"status": "planning"},
    )
    await repo.record_research_event(second)
    await repo.record_research_event(first)

    events = await repo.list_research_events("task_evt")
    assert [e["type"] for e in events] == ["status", "tool_call"]
    # every persisted payload re-validates against the typed event union
    parsed = [RESEARCH_EVENT_ADAPTER.validate_python(e) for e in events]
    assert parsed[1].payload.tool_name == "paper_search"
    assert await repo.list_research_events("task_missing") == []
