"""SQLite-backed implementation of the Research OS persistence contract.

The repository borrows the connection and lock from the existing `SQLiteStore`,
so Research OS writes stay serialised with legacy task/event writes.

Model <-> row mapping is handled by one generic codec (`_encode_row` /
`_decode_row`) driven by the per-table column lists below. The single
convention it relies on: a column whose name ends in `_json` stores a
JSON-encoded list/dict field; every other column maps 1:1 to a model field of
the same name. datetimes and enums are coerced by the codec and by Pydantic.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from enum import Enum
from typing import TypeVar
from uuid import uuid4

import aiosqlite
from pydantic import BaseModel

from athena.research.domain import (
    BaselineCandidate,
    Benchmark,
    Claim,
    Evidence,
    MethodTaxonomy,
    Paper,
    PaperNote,
    PaperScreeningStatus,
    ResearchIdea,
    ResearchProject,
    ReviewCheckpoint,
)
from athena.research.events import ResearchEvent
from athena.research.tools import ToolCallRecord, ToolObservationRecord, utcnow

from .repository import ResearchRepository

# Research OS tables. Applied with CREATE TABLE IF NOT EXISTS so re-running it
# on an existing database is a no-op. List/dict domain fields are stored as
# JSON text columns; datetimes as ISO strings; ids as TEXT primary keys.
RESEARCH_OS_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_projects (
    id                TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    research_question TEXT NOT NULL,
    field             TEXT,
    constraints_json  TEXT NOT NULL,
    target_venue      TEXT,
    status            TEXT NOT NULL,
    owner             TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    id                    TEXT PRIMARY KEY,
    project_id            TEXT NOT NULL,
    title                 TEXT NOT NULL,
    authors_json          TEXT NOT NULL,
    year                  INTEGER,
    venue                 TEXT,
    abstract              TEXT,
    url                   TEXT,
    pdf_url               TEXT,
    arxiv_id              TEXT,
    doi                   TEXT,
    semantic_scholar_id   TEXT,
    citation_count        INTEGER,
    code_url              TEXT,
    dataset_mentions_json TEXT NOT NULL,
    screening_status      TEXT NOT NULL,
    relevance_score       REAL,
    created_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_notes (
    id                      TEXT PRIMARY KEY,
    paper_id                TEXT NOT NULL,
    problem                 TEXT,
    method                  TEXT,
    training_setup          TEXT,
    datasets_json           TEXT NOT NULL,
    metrics_json            TEXT NOT NULL,
    baselines_json          TEXT NOT NULL,
    main_results            TEXT,
    limitations             TEXT,
    reproducibility_notes   TEXT,
    important_sections_json TEXT NOT NULL,
    created_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id                TEXT PRIMARY KEY,
    project_id        TEXT NOT NULL,
    text              TEXT NOT NULL,
    claim_type        TEXT NOT NULL,
    paper_id          TEXT,
    section           TEXT,
    confidence        REAL,
    evidence_ids_json TEXT NOT NULL,
    status            TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id                  TEXT PRIMARY KEY,
    claim_id            TEXT NOT NULL,
    source_type         TEXT NOT NULL,
    source_url          TEXT,
    paper_id            TEXT,
    section             TEXT,
    quote               TEXT,
    normalized_text     TEXT,
    confidence          REAL,
    verification_status TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS method_taxonomies (
    id                 TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL,
    nodes_json         TEXT NOT NULL,
    edges_json         TEXT NOT NULL,
    summary            TEXT,
    open_problems_json TEXT NOT NULL,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS baseline_candidates (
    id                      TEXT PRIMARY KEY,
    project_id              TEXT NOT NULL,
    name                    TEXT NOT NULL,
    method_summary          TEXT NOT NULL,
    paper_id                TEXT,
    code_url                TEXT,
    dataset                 TEXT,
    metric                  TEXT,
    reported_score          TEXT,
    reproduction_difficulty TEXT,
    hardware_requirement    TEXT,
    expected_runtime        TEXT,
    license                 TEXT,
    rank_score              REAL,
    selection_reason        TEXT,
    status                  TEXT NOT NULL,
    created_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_ideas (
    id                      TEXT PRIMARY KEY,
    project_id              TEXT NOT NULL,
    title                   TEXT NOT NULL,
    motivation              TEXT NOT NULL,
    core_hypothesis         TEXT NOT NULL,
    method_sketch           TEXT NOT NULL,
    expected_advantage      TEXT,
    required_baselines_json TEXT NOT NULL,
    required_datasets_json  TEXT NOT NULL,
    evaluation_plan         TEXT,
    novelty_score           REAL,
    feasibility_score       REAL,
    risk_score              REAL,
    overall_score           REAL,
    evidence_ids_json       TEXT NOT NULL,
    status                  TEXT NOT NULL,
    created_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS benchmarks (
    id                    TEXT PRIMARY KEY,
    project_id            TEXT NOT NULL,
    name                  TEXT NOT NULL,
    dataset               TEXT NOT NULL,
    metrics_json          TEXT NOT NULL,
    task                  TEXT,
    source_paper_ids_json TEXT NOT NULL,
    adoption_count        INTEGER NOT NULL,
    status                TEXT NOT NULL,
    selection_reason      TEXT,
    created_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_specs (
    id                    TEXT PRIMARY KEY,
    project_id            TEXT NOT NULL,
    task                  TEXT NOT NULL,
    idea_id               TEXT,
    baseline_id           TEXT,
    dataset               TEXT,
    metrics_json          TEXT NOT NULL,
    train_command         TEXT,
    eval_command          TEXT,
    config_json           TEXT NOT NULL,
    expected_outputs_json TEXT NOT NULL,
    hardware_requirement  TEXT,
    seed_plan_json        TEXT NOT NULL,
    ablation_plan_json    TEXT NOT NULL,
    created_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_runs (
    id                 TEXT PRIMARY KEY,
    experiment_spec_id TEXT NOT NULL,
    status             TEXT NOT NULL,
    started_at         TEXT,
    ended_at           TEXT,
    command            TEXT,
    exit_code          INTEGER,
    stdout_path        TEXT,
    stderr_path        TEXT,
    metrics_json       TEXT NOT NULL,
    artifacts_json     TEXT NOT NULL,
    failure_reason     TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS code_artifacts (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL,
    path                TEXT NOT NULL,
    artifact_type       TEXT NOT NULL,
    language            TEXT,
    source              TEXT,
    related_baseline_id TEXT,
    related_idea_id     TEXT,
    checksum            TEXT,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id               TEXT PRIMARY KEY,
    task_id          TEXT NOT NULL,
    project_id       TEXT,
    tool_name        TEXT NOT NULL,
    arguments_json   TEXT NOT NULL,
    permission_level TEXT NOT NULL,
    approval_status  TEXT NOT NULL,
    status           TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    started_at       TEXT,
    finished_at      TEXT
);

CREATE TABLE IF NOT EXISTS tool_observations (
    id                     TEXT PRIMARY KEY,
    tool_call_id           TEXT NOT NULL,
    status                 TEXT NOT NULL,
    summary                TEXT NOT NULL,
    structured_output_json TEXT NOT NULL,
    raw_output_ref         TEXT,
    error                  TEXT,
    created_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_checkpoints (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    project_id      TEXT NOT NULL,
    checkpoint_type TEXT NOT NULL,
    title           TEXT NOT NULL,
    content_json    TEXT NOT NULL,
    status          TEXT NOT NULL,
    decision        TEXT,
    comment         TEXT,
    created_at      TEXT NOT NULL,
    decided_at      TEXT
);

CREATE TABLE IF NOT EXISTS research_events (
    id           TEXT PRIMARY KEY,
    task_id      TEXT NOT NULL,
    project_id   TEXT,
    seq          INTEGER NOT NULL,
    type         TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    timestamp    TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_research_projects_updated ON research_projects(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_papers_project ON papers(project_id);
CREATE INDEX IF NOT EXISTS idx_paper_notes_paper ON paper_notes(paper_id);
CREATE INDEX IF NOT EXISTS idx_claims_project ON claims(project_id);
CREATE INDEX IF NOT EXISTS idx_claims_paper ON claims(paper_id);
CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_method_taxonomies_project ON method_taxonomies(project_id);
CREATE INDEX IF NOT EXISTS idx_baseline_candidates_project ON baseline_candidates(project_id);
CREATE INDEX IF NOT EXISTS idx_research_ideas_project ON research_ideas(project_id);
CREATE INDEX IF NOT EXISTS idx_benchmarks_project ON benchmarks(project_id, adoption_count DESC);
CREATE INDEX IF NOT EXISTS idx_experiment_specs_project ON experiment_specs(project_id);
CREATE INDEX IF NOT EXISTS idx_experiment_runs_spec ON experiment_runs(experiment_spec_id);
CREATE INDEX IF NOT EXISTS idx_code_artifacts_project ON code_artifacts(project_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_task ON tool_calls(task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_project ON tool_calls(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_status ON tool_calls(status);
CREATE INDEX IF NOT EXISTS idx_tool_observations_call ON tool_observations(tool_call_id, created_at);
CREATE INDEX IF NOT EXISTS idx_review_checkpoints_project ON review_checkpoints(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_review_checkpoints_task ON review_checkpoints(task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_review_checkpoints_status ON review_checkpoints(status);
CREATE INDEX IF NOT EXISTS idx_research_events_task ON research_events(task_id, seq);
CREATE INDEX IF NOT EXISTS idx_research_events_project ON research_events(project_id, seq);
"""

# Each column list is the single source of truth for a table, shared by its
# INSERT, SELECT and the row codec. A `_json` suffix marks a JSON text column.
_PROJECT_COLUMNS = (
    "id, title, research_question, field, constraints_json, "
    "target_venue, status, owner, created_at, updated_at"
)
_PAPER_COLUMNS = (
    "id, project_id, title, authors_json, year, venue, abstract, url, pdf_url, "
    "arxiv_id, doi, semantic_scholar_id, citation_count, code_url, "
    "dataset_mentions_json, screening_status, relevance_score, created_at"
)
_PAPER_NOTE_COLUMNS = (
    "id, paper_id, problem, method, training_setup, datasets_json, metrics_json, "
    "baselines_json, main_results, limitations, reproducibility_notes, "
    "important_sections_json, created_at"
)
_TOOL_CALL_COLUMNS = (
    "id, task_id, project_id, tool_name, arguments_json, permission_level, "
    "approval_status, status, created_at, started_at, finished_at"
)
_TOOL_OBSERVATION_COLUMNS = (
    "id, tool_call_id, status, summary, structured_output_json, raw_output_ref, "
    "error, created_at"
)
_CLAIM_COLUMNS = (
    "id, project_id, text, claim_type, paper_id, section, confidence, "
    "evidence_ids_json, status, created_at"
)
_EVIDENCE_COLUMNS = (
    "id, claim_id, source_type, source_url, paper_id, section, quote, "
    "normalized_text, confidence, verification_status, created_at"
)
_CHECKPOINT_COLUMNS = (
    "id, task_id, project_id, checkpoint_type, title, content_json, status, "
    "decision, comment, created_at, decided_at"
)
_RESEARCH_EVENT_COLUMNS = (
    "id, task_id, project_id, seq, type, payload_json, timestamp, created_at"
)
_TAXONOMY_COLUMNS = (
    "id, project_id, nodes_json, edges_json, summary, open_problems_json, created_at"
)
_BASELINE_COLUMNS = (
    "id, project_id, name, method_summary, paper_id, code_url, dataset, metric, "
    "reported_score, reproduction_difficulty, hardware_requirement, expected_runtime, "
    "license, rank_score, selection_reason, status, created_at"
)
_IDEA_COLUMNS = (
    "id, project_id, title, motivation, core_hypothesis, method_sketch, "
    "expected_advantage, required_baselines_json, required_datasets_json, "
    "evaluation_plan, novelty_score, feasibility_score, risk_score, overall_score, "
    "evidence_ids_json, status, created_at"
)
_BENCHMARK_COLUMNS = (
    "id, project_id, name, dataset, metrics_json, task, source_paper_ids_json, "
    "adoption_count, status, selection_reason, created_at"
)

_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _id(prefix: str) -> str:
    """Generate a prefixed unique id for rows that have no model-level id."""
    return f"{prefix}_{uuid4().hex}"


def _columns(spec: str) -> list[str]:
    return [name.strip() for name in spec.split(",")]


def _prefixed(spec: str, table: str) -> str:
    """Qualify a column list with a table name (for JOIN SELECTs)."""
    return ", ".join(f"{table}.{name}" for name in _columns(spec))


def _placeholders(spec: str) -> str:
    """Return the `?, ?, ...` placeholder list matching a column spec."""
    return ", ".join("?" for _ in _columns(spec))


def _datetime_to_iso_utc(dt: datetime) -> str:
    """Normalize a datetime to UTC and return a fixed-width ISO 8601 string.

    Naive datetimes are assumed to already be UTC; aware datetimes are
    converted. Always emitting a `+00:00` offset with microsecond precision
    keeps lexicographic ordering (ORDER BY a TEXT column) consistent with true
    chronological ordering.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="microseconds")


def _encode_row(model: BaseModel, columns: str) -> tuple[object, ...]:
    """Serialize a model to a positional row matching `columns`.

    `*_json` columns receive the JSON-encoded field; datetimes become ISO UTC
    strings and enums their value. The inverse of `_decode_row`.
    """
    values: list[object] = []
    for column in _columns(columns):
        if column.endswith("_json"):
            field = getattr(model, column[:-5])
            values.append(json.dumps(field, ensure_ascii=False, default=str))
            continue
        value = getattr(model, column)
        if isinstance(value, datetime):
            value = _datetime_to_iso_utc(value)
        elif isinstance(value, Enum):
            value = value.value
        values.append(value)
    return tuple(values)


def _decode_row(model_cls: type[_ModelT], columns: str, row: tuple) -> _ModelT:
    """Reconstruct a model from a positional row matching `columns`.

    `*_json` columns are JSON-decoded; Pydantic coerces ISO datetime and
    enum-value strings back on validation. The inverse of `_encode_row`.
    """
    data: dict[str, object] = {}
    for column, value in zip(_columns(columns), row, strict=True):
        if column.endswith("_json"):
            data[column[:-5]] = json.loads(value)
        else:
            data[column] = value
    return model_cls.model_validate(data)


class ResearchSQLiteRepository(ResearchRepository):
    """Stores Research OS domain models in the shared SQLite database.

    Created by `SQLiteStore.research_repository()` with the store's own
    connection and lock, so it never opens a second database connection.
    """

    def __init__(self, conn: aiosqlite.Connection, lock: asyncio.Lock) -> None:
        self._conn = conn
        self._lock = lock

    async def _insert(self, table: str, columns: str, model: BaseModel) -> None:
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO {table}({columns}) VALUES({_placeholders(columns)})",
                _encode_row(model, columns),
            )
            await self._conn.commit()

    async def _upsert(self, table: str, columns: str, model: BaseModel, *, mutable: str) -> None:
        """Insert `model`, or update the listed `mutable` columns on id conflict."""
        assignments = ", ".join(f"{name} = excluded.{name}" for name in _columns(mutable))
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO {table}({columns}) VALUES({_placeholders(columns)}) "
                f"ON CONFLICT(id) DO UPDATE SET {assignments}",
                _encode_row(model, columns),
            )
            await self._conn.commit()

    async def _fetch_one(self, sql: str, params: tuple) -> tuple | None:
        async with self._lock:
            cursor = await self._conn.execute(sql, params)
            row = await cursor.fetchone()
            await cursor.close()
        return row

    async def _fetch_all(self, sql: str, params: tuple) -> list[tuple]:
        async with self._lock:
            cursor = await self._conn.execute(sql, params)
            rows = await cursor.fetchall()
            await cursor.close()
        return list(rows)

    # --- projects --------------------------------------------------------

    async def create_project(self, project: ResearchProject) -> None:
        await self._insert("research_projects", _PROJECT_COLUMNS, project)

    async def upsert_project(self, project: ResearchProject) -> None:
        await self._upsert(
            "research_projects",
            _PROJECT_COLUMNS,
            project,
            mutable="title, research_question, field, constraints_json, "
            "target_venue, status, owner, updated_at",
        )

    async def get_project(self, project_id: str) -> ResearchProject | None:
        row = await self._fetch_one(
            f"SELECT {_PROJECT_COLUMNS} FROM research_projects WHERE id = ?",
            (project_id,),
        )
        return _decode_row(ResearchProject, _PROJECT_COLUMNS, row) if row else None

    async def list_projects(self, limit: int = 50) -> list[ResearchProject]:
        rows = await self._fetch_all(
            f"SELECT {_PROJECT_COLUMNS} FROM research_projects "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )
        return [_decode_row(ResearchProject, _PROJECT_COLUMNS, row) for row in rows]

    # --- papers ----------------------------------------------------------

    async def create_paper(self, paper: Paper) -> None:
        await self._insert("papers", _PAPER_COLUMNS, paper)

    async def upsert_paper(self, paper: Paper) -> None:
        await self._upsert(
            "papers",
            _PAPER_COLUMNS,
            paper,
            mutable="project_id, title, authors_json, year, venue, abstract, url, "
            "pdf_url, arxiv_id, doi, semantic_scholar_id, citation_count, code_url, "
            "dataset_mentions_json, screening_status, relevance_score, created_at",
        )

    async def get_paper(self, paper_id: str) -> Paper | None:
        row = await self._fetch_one(
            f"SELECT {_PAPER_COLUMNS} FROM papers WHERE id = ?", (paper_id,)
        )
        return _decode_row(Paper, _PAPER_COLUMNS, row) if row else None

    async def list_project_papers(
        self,
        project_id: str,
        *,
        limit: int = 100,
        screening_status: PaperScreeningStatus | None = None,
    ) -> list[Paper]:
        sql = f"SELECT {_PAPER_COLUMNS} FROM papers WHERE project_id = ? "
        params: tuple[object, ...] = (project_id,)
        if screening_status is not None:
            sql += "AND screening_status = ? "
            params += (screening_status.value,)
        rows = await self._fetch_all(sql + "ORDER BY created_at DESC LIMIT ?", params + (limit,))
        return [_decode_row(Paper, _PAPER_COLUMNS, row) for row in rows]

    # --- paper notes -----------------------------------------------------

    async def create_paper_note(self, note: PaperNote) -> None:
        await self._insert("paper_notes", _PAPER_NOTE_COLUMNS, note)

    async def upsert_paper_note(self, note: PaperNote) -> None:
        await self._upsert(
            "paper_notes",
            _PAPER_NOTE_COLUMNS,
            note,
            mutable="paper_id, problem, method, training_setup, datasets_json, "
            "metrics_json, baselines_json, main_results, limitations, "
            "reproducibility_notes, important_sections_json, created_at",
        )

    async def get_paper_note(self, note_id: str) -> PaperNote | None:
        row = await self._fetch_one(
            f"SELECT {_PAPER_NOTE_COLUMNS} FROM paper_notes WHERE id = ?", (note_id,)
        )
        return _decode_row(PaperNote, _PAPER_NOTE_COLUMNS, row) if row else None

    async def list_paper_notes(self, paper_id: str) -> list[PaperNote]:
        rows = await self._fetch_all(
            f"SELECT {_PAPER_NOTE_COLUMNS} FROM paper_notes WHERE paper_id = ? "
            "ORDER BY created_at DESC",
            (paper_id,),
        )
        return [_decode_row(PaperNote, _PAPER_NOTE_COLUMNS, row) for row in rows]

    # --- tool trace ------------------------------------------------------

    async def record_tool_call(self, call: ToolCallRecord) -> None:
        await self._insert("tool_calls", _TOOL_CALL_COLUMNS, call)

    async def record_tool_observation(self, observation: ToolObservationRecord) -> None:
        await self._insert("tool_observations", _TOOL_OBSERVATION_COLUMNS, observation)

    async def list_tool_calls(self, task_id: str) -> list[ToolCallRecord]:
        rows = await self._fetch_all(
            f"SELECT {_TOOL_CALL_COLUMNS} FROM tool_calls WHERE task_id = ? "
            "ORDER BY created_at ASC",
            (task_id,),
        )
        return [_decode_row(ToolCallRecord, _TOOL_CALL_COLUMNS, row) for row in rows]

    async def list_project_tool_calls(self, project_id: str) -> list[ToolCallRecord]:
        rows = await self._fetch_all(
            f"SELECT {_TOOL_CALL_COLUMNS} FROM tool_calls WHERE project_id = ? "
            "ORDER BY created_at ASC",
            (project_id,),
        )
        return [_decode_row(ToolCallRecord, _TOOL_CALL_COLUMNS, row) for row in rows]

    async def list_tool_observations(self, tool_call_id: str) -> list[ToolObservationRecord]:
        rows = await self._fetch_all(
            f"SELECT {_TOOL_OBSERVATION_COLUMNS} FROM tool_observations "
            "WHERE tool_call_id = ? ORDER BY created_at ASC",
            (tool_call_id,),
        )
        return [_decode_row(ToolObservationRecord, _TOOL_OBSERVATION_COLUMNS, row) for row in rows]

    async def list_tool_observations_for_calls(
        self,
        tool_call_ids: list[str],
    ) -> dict[str, list[ToolObservationRecord]]:
        if not tool_call_ids:
            return {}
        placeholders = ", ".join("?" for _ in tool_call_ids)
        rows = await self._fetch_all(
            f"SELECT {_TOOL_OBSERVATION_COLUMNS} FROM tool_observations "
            f"WHERE tool_call_id IN ({placeholders}) "
            "ORDER BY tool_call_id ASC, created_at ASC",
            tuple(tool_call_ids),
        )
        grouped: dict[str, list[ToolObservationRecord]] = {cid: [] for cid in tool_call_ids}
        for row in rows:
            observation = _decode_row(ToolObservationRecord, _TOOL_OBSERVATION_COLUMNS, row)
            grouped.setdefault(observation.tool_call_id, []).append(observation)
        return grouped

    # --- claims ----------------------------------------------------------

    async def create_claim(self, claim: Claim) -> None:
        await self._insert("claims", _CLAIM_COLUMNS, claim)

    async def upsert_claim(self, claim: Claim) -> None:
        await self._upsert(
            "claims",
            _CLAIM_COLUMNS,
            claim,
            mutable="project_id, text, claim_type, paper_id, section, confidence, "
            "evidence_ids_json, status",
        )

    async def get_claim(self, claim_id: str) -> Claim | None:
        row = await self._fetch_one(
            f"SELECT {_CLAIM_COLUMNS} FROM claims WHERE id = ?", (claim_id,)
        )
        return _decode_row(Claim, _CLAIM_COLUMNS, row) if row else None

    async def list_project_claims(self, project_id: str, *, limit: int = 500) -> list[Claim]:
        rows = await self._fetch_all(
            f"SELECT {_CLAIM_COLUMNS} FROM claims WHERE project_id = ? "
            "ORDER BY created_at ASC LIMIT ?",
            (project_id, limit),
        )
        return [_decode_row(Claim, _CLAIM_COLUMNS, row) for row in rows]

    async def list_paper_claims(self, paper_id: str) -> list[Claim]:
        rows = await self._fetch_all(
            f"SELECT {_CLAIM_COLUMNS} FROM claims WHERE paper_id = ? ORDER BY created_at ASC",
            (paper_id,),
        )
        return [_decode_row(Claim, _CLAIM_COLUMNS, row) for row in rows]

    # --- evidence --------------------------------------------------------

    async def create_evidence(self, evidence: Evidence) -> None:
        await self._insert("evidence", _EVIDENCE_COLUMNS, evidence)

    async def get_evidence(self, evidence_id: str) -> Evidence | None:
        row = await self._fetch_one(
            f"SELECT {_EVIDENCE_COLUMNS} FROM evidence WHERE id = ?", (evidence_id,)
        )
        return _decode_row(Evidence, _EVIDENCE_COLUMNS, row) if row else None

    async def list_claim_evidence(self, claim_id: str) -> list[Evidence]:
        rows = await self._fetch_all(
            f"SELECT {_EVIDENCE_COLUMNS} FROM evidence WHERE claim_id = ? "
            "ORDER BY created_at ASC",
            (claim_id,),
        )
        return [_decode_row(Evidence, _EVIDENCE_COLUMNS, row) for row in rows]

    async def list_project_evidence(self, project_id: str) -> list[Evidence]:
        rows = await self._fetch_all(
            f"SELECT {_prefixed(_EVIDENCE_COLUMNS, 'evidence')} FROM evidence "
            "JOIN claims ON evidence.claim_id = claims.id "
            "WHERE claims.project_id = ? ORDER BY evidence.created_at ASC",
            (project_id,),
        )
        return [_decode_row(Evidence, _EVIDENCE_COLUMNS, row) for row in rows]

    # --- review checkpoints ---------------------------------------------

    async def create_checkpoint(self, checkpoint: ReviewCheckpoint) -> None:
        await self._insert("review_checkpoints", _CHECKPOINT_COLUMNS, checkpoint)

    async def upsert_checkpoint(self, checkpoint: ReviewCheckpoint) -> None:
        await self._upsert(
            "review_checkpoints",
            _CHECKPOINT_COLUMNS,
            checkpoint,
            mutable="task_id, project_id, checkpoint_type, title, content_json, "
            "status, decision, comment, decided_at",
        )

    async def get_checkpoint(self, checkpoint_id: str) -> ReviewCheckpoint | None:
        row = await self._fetch_one(
            f"SELECT {_CHECKPOINT_COLUMNS} FROM review_checkpoints WHERE id = ?",
            (checkpoint_id,),
        )
        return _decode_row(ReviewCheckpoint, _CHECKPOINT_COLUMNS, row) if row else None

    async def list_project_checkpoints(self, project_id: str) -> list[ReviewCheckpoint]:
        rows = await self._fetch_all(
            f"SELECT {_CHECKPOINT_COLUMNS} FROM review_checkpoints WHERE project_id = ? "
            "ORDER BY created_at ASC",
            (project_id,),
        )
        return [_decode_row(ReviewCheckpoint, _CHECKPOINT_COLUMNS, row) for row in rows]

    # --- research events -------------------------------------------------

    async def record_research_event(self, event: ResearchEvent) -> None:
        row = (
            _id("evt"),
            event.task_id,
            event.project_id,
            event.seq,
            event.type,
            json.dumps(event.model_dump(mode="json"), ensure_ascii=False, default=str),
            _datetime_to_iso_utc(event.timestamp),
            _datetime_to_iso_utc(utcnow()),
        )
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO research_events({_RESEARCH_EVENT_COLUMNS}) "
                f"VALUES({_placeholders(_RESEARCH_EVENT_COLUMNS)})",
                row,
            )
            await self._conn.commit()

    async def list_research_events(self, task_id: str) -> list[dict]:
        rows = await self._fetch_all(
            "SELECT payload_json FROM research_events WHERE task_id = ? "
            "ORDER BY seq ASC, created_at ASC",
            (task_id,),
        )
        return [json.loads(row[0]) for row in rows]

    # --- method taxonomies ----------------------------------------------

    async def create_taxonomy(self, taxonomy: MethodTaxonomy) -> None:
        await self._insert("method_taxonomies", _TAXONOMY_COLUMNS, taxonomy)

    async def get_taxonomy(self, taxonomy_id: str) -> MethodTaxonomy | None:
        row = await self._fetch_one(
            f"SELECT {_TAXONOMY_COLUMNS} FROM method_taxonomies WHERE id = ?",
            (taxonomy_id,),
        )
        return _decode_row(MethodTaxonomy, _TAXONOMY_COLUMNS, row) if row else None

    async def latest_project_taxonomy(self, project_id: str) -> MethodTaxonomy | None:
        row = await self._fetch_one(
            f"SELECT {_TAXONOMY_COLUMNS} FROM method_taxonomies WHERE project_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        )
        return _decode_row(MethodTaxonomy, _TAXONOMY_COLUMNS, row) if row else None

    # --- baseline candidates --------------------------------------------

    async def create_baseline(self, baseline: BaselineCandidate) -> None:
        await self._insert("baseline_candidates", _BASELINE_COLUMNS, baseline)

    async def upsert_baseline(self, baseline: BaselineCandidate) -> None:
        await self._upsert(
            "baseline_candidates",
            _BASELINE_COLUMNS,
            baseline,
            mutable="project_id, name, method_summary, paper_id, code_url, dataset, "
            "metric, reported_score, reproduction_difficulty, hardware_requirement, "
            "expected_runtime, license, rank_score, selection_reason, status",
        )

    async def get_baseline(self, baseline_id: str) -> BaselineCandidate | None:
        row = await self._fetch_one(
            f"SELECT {_BASELINE_COLUMNS} FROM baseline_candidates WHERE id = ?",
            (baseline_id,),
        )
        return _decode_row(BaselineCandidate, _BASELINE_COLUMNS, row) if row else None

    async def list_project_baselines(self, project_id: str) -> list[BaselineCandidate]:
        rows = await self._fetch_all(
            f"SELECT {_BASELINE_COLUMNS} FROM baseline_candidates WHERE project_id = ? "
            "ORDER BY created_at ASC",
            (project_id,),
        )
        return [_decode_row(BaselineCandidate, _BASELINE_COLUMNS, row) for row in rows]

    # --- research ideas -------------------------------------------------

    async def create_idea(self, idea: ResearchIdea) -> None:
        await self._insert("research_ideas", _IDEA_COLUMNS, idea)

    async def upsert_idea(self, idea: ResearchIdea) -> None:
        await self._upsert(
            "research_ideas",
            _IDEA_COLUMNS,
            idea,
            mutable="project_id, title, motivation, core_hypothesis, method_sketch, "
            "expected_advantage, required_baselines_json, required_datasets_json, "
            "evaluation_plan, novelty_score, feasibility_score, risk_score, "
            "overall_score, evidence_ids_json, status",
        )

    async def get_idea(self, idea_id: str) -> ResearchIdea | None:
        row = await self._fetch_one(
            f"SELECT {_IDEA_COLUMNS} FROM research_ideas WHERE id = ?", (idea_id,)
        )
        return _decode_row(ResearchIdea, _IDEA_COLUMNS, row) if row else None

    async def list_project_ideas(self, project_id: str) -> list[ResearchIdea]:
        rows = await self._fetch_all(
            f"SELECT {_IDEA_COLUMNS} FROM research_ideas WHERE project_id = ? "
            "ORDER BY created_at ASC",
            (project_id,),
        )
        return [_decode_row(ResearchIdea, _IDEA_COLUMNS, row) for row in rows]

    # --- benchmarks -----------------------------------------------------

    async def create_benchmark(self, benchmark: Benchmark) -> None:
        await self._insert("benchmarks", _BENCHMARK_COLUMNS, benchmark)

    async def upsert_benchmark(self, benchmark: Benchmark) -> None:
        await self._upsert(
            "benchmarks",
            _BENCHMARK_COLUMNS,
            benchmark,
            mutable="project_id, name, dataset, metrics_json, task, "
            "source_paper_ids_json, adoption_count, status, selection_reason",
        )

    async def get_benchmark(self, benchmark_id: str) -> Benchmark | None:
        row = await self._fetch_one(
            f"SELECT {_BENCHMARK_COLUMNS} FROM benchmarks WHERE id = ?", (benchmark_id,)
        )
        return _decode_row(Benchmark, _BENCHMARK_COLUMNS, row) if row else None

    async def list_project_benchmarks(self, project_id: str) -> list[Benchmark]:
        """Return a project's benchmarks ranked by adoption (most-used first)."""
        rows = await self._fetch_all(
            f"SELECT {_BENCHMARK_COLUMNS} FROM benchmarks WHERE project_id = ? "
            "ORDER BY adoption_count DESC, created_at ASC",
            (project_id,),
        )
        return [_decode_row(Benchmark, _BENCHMARK_COLUMNS, row) for row in rows]
