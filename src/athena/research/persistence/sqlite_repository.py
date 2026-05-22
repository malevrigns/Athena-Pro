"""SQLite-backed implementation of the Research OS persistence contract.

The repository does not own the database connection — it borrows the
connection and lock from the existing `SQLiteStore`, so Research OS writes
stay serialised with legacy task/event writes. Serialization is explicit
(column by column) so schema drift fails loudly instead of silently.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

import aiosqlite

from athena.research.domain import (
    CheckpointStatus,
    CheckpointType,
    Claim,
    Evidence,
    Paper,
    PaperNote,
    PaperScreeningStatus,
    ProjectStatus,
    ResearchProject,
    ReviewCheckpoint,
    ReviewDecision,
)
from athena.research.events import ResearchEvent
from athena.research.tools import (
    PermissionLevel,
    ToolCallRecord,
    ToolCallStatus,
    ToolObservationRecord,
    ToolObservationStatus,
    utcnow,
)

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

# Column order is the single source of truth shared by INSERT, SELECT and the
# row (de)serialization helpers below — keep all four in sync.
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


def _id(prefix: str) -> str:
    """Generate a prefixed unique id for rows that have no model-level id."""
    return f"{prefix}_{uuid4().hex}"


def _prefixed(columns: str, table: str) -> str:
    """Qualify a comma-separated column list with a table name (for JOIN SELECTs)."""
    return ", ".join(f"{table}.{name.strip()}" for name in columns.split(","))


def _datetime_to_iso_utc(dt: datetime) -> str:
    """Normalize a datetime to UTC and return a fixed-width ISO 8601 string.

    Naive datetimes are assumed to already be UTC; aware datetimes are
    converted. Always emitting a `+00:00` offset with microsecond precision
    keeps the lexicographic ordering used by `list_projects` (ORDER BY a TEXT
    column) consistent with true chronological ordering.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="microseconds")


def _project_to_row(project: ResearchProject) -> tuple[object, ...]:
    """Map a ResearchProject to a positional row matching `_PROJECT_COLUMNS`."""
    return (
        project.id,
        project.title,
        project.research_question,
        project.field,
        json.dumps(project.constraints, ensure_ascii=False),
        project.target_venue,
        project.status.value,
        project.owner,
        _datetime_to_iso_utc(project.created_at),
        _datetime_to_iso_utc(project.updated_at),
    )


def _row_to_project(row: tuple) -> ResearchProject:
    """Reconstruct a ResearchProject from a `_PROJECT_COLUMNS` row."""
    return ResearchProject(
        id=row[0],
        title=row[1],
        research_question=row[2],
        field=row[3],
        constraints=json.loads(row[4]),
        target_venue=row[5],
        status=ProjectStatus(row[6]),
        owner=row[7],
        created_at=datetime.fromisoformat(row[8]),
        updated_at=datetime.fromisoformat(row[9]),
    )


def _paper_to_row(paper: Paper) -> tuple[object, ...]:
    return (
        paper.id,
        paper.project_id,
        paper.title,
        json.dumps(paper.authors, ensure_ascii=False),
        paper.year,
        paper.venue,
        paper.abstract,
        paper.url,
        paper.pdf_url,
        paper.arxiv_id,
        paper.doi,
        paper.semantic_scholar_id,
        paper.citation_count,
        paper.code_url,
        json.dumps(paper.dataset_mentions, ensure_ascii=False),
        paper.screening_status.value,
        paper.relevance_score,
        _datetime_to_iso_utc(paper.created_at),
    )


def _row_to_paper(row: tuple) -> Paper:
    return Paper(
        id=row[0],
        project_id=row[1],
        title=row[2],
        authors=json.loads(row[3]),
        year=row[4],
        venue=row[5],
        abstract=row[6],
        url=row[7],
        pdf_url=row[8],
        arxiv_id=row[9],
        doi=row[10],
        semantic_scholar_id=row[11],
        citation_count=row[12],
        code_url=row[13],
        dataset_mentions=json.loads(row[14]),
        screening_status=PaperScreeningStatus(row[15]),
        relevance_score=row[16],
        created_at=datetime.fromisoformat(row[17]),
    )


def _paper_note_to_row(note: PaperNote) -> tuple[object, ...]:
    return (
        note.id,
        note.paper_id,
        note.problem,
        note.method,
        note.training_setup,
        json.dumps(note.datasets, ensure_ascii=False),
        json.dumps(note.metrics, ensure_ascii=False),
        json.dumps(note.baselines, ensure_ascii=False),
        note.main_results,
        note.limitations,
        note.reproducibility_notes,
        json.dumps(note.important_sections, ensure_ascii=False),
        _datetime_to_iso_utc(note.created_at),
    )


def _row_to_paper_note(row: tuple) -> PaperNote:
    return PaperNote(
        id=row[0],
        paper_id=row[1],
        problem=row[2],
        method=row[3],
        training_setup=row[4],
        datasets=json.loads(row[5]),
        metrics=json.loads(row[6]),
        baselines=json.loads(row[7]),
        main_results=row[8],
        limitations=row[9],
        reproducibility_notes=row[10],
        important_sections=json.loads(row[11]),
        created_at=datetime.fromisoformat(row[12]),
    )


def _tool_call_to_row(call: ToolCallRecord) -> tuple[object, ...]:
    return (
        call.id,
        call.task_id,
        call.project_id,
        call.tool_name,
        json.dumps(call.arguments, ensure_ascii=False, default=str),
        call.permission_level.value,
        call.approval_status,
        call.status.value,
        _datetime_to_iso_utc(call.created_at),
        _datetime_to_iso_utc(call.started_at) if call.started_at else None,
        _datetime_to_iso_utc(call.finished_at) if call.finished_at else None,
    )


def _row_to_tool_call(row: tuple) -> ToolCallRecord:
    return ToolCallRecord(
        id=row[0],
        task_id=row[1],
        project_id=row[2],
        tool_name=row[3],
        arguments=json.loads(row[4]),
        permission_level=PermissionLevel(row[5]),
        approval_status=row[6],
        status=ToolCallStatus(row[7]),
        created_at=datetime.fromisoformat(row[8]),
        started_at=datetime.fromisoformat(row[9]) if row[9] else None,
        finished_at=datetime.fromisoformat(row[10]) if row[10] else None,
    )


def _tool_observation_to_row(observation: ToolObservationRecord) -> tuple[object, ...]:
    return (
        observation.id,
        observation.tool_call_id,
        observation.status.value,
        observation.summary,
        json.dumps(observation.structured_output, ensure_ascii=False, default=str),
        observation.raw_output_ref,
        observation.error,
        _datetime_to_iso_utc(observation.created_at),
    )


def _row_to_tool_observation(row: tuple) -> ToolObservationRecord:
    return ToolObservationRecord(
        id=row[0],
        tool_call_id=row[1],
        status=ToolObservationStatus(row[2]),
        summary=row[3],
        structured_output=json.loads(row[4]),
        raw_output_ref=row[5],
        error=row[6],
        created_at=datetime.fromisoformat(row[7]),
    )


def _claim_to_row(claim: Claim) -> tuple[object, ...]:
    return (
        claim.id,
        claim.project_id,
        claim.text,
        claim.claim_type,
        claim.paper_id,
        claim.section,
        claim.confidence,
        json.dumps(claim.evidence_ids, ensure_ascii=False),
        claim.status,
        _datetime_to_iso_utc(claim.created_at),
    )


def _row_to_claim(row: tuple) -> Claim:
    return Claim(
        id=row[0],
        project_id=row[1],
        text=row[2],
        claim_type=row[3],
        paper_id=row[4],
        section=row[5],
        confidence=row[6],
        evidence_ids=json.loads(row[7]),
        status=row[8],
        created_at=datetime.fromisoformat(row[9]),
    )


def _evidence_to_row(evidence: Evidence) -> tuple[object, ...]:
    return (
        evidence.id,
        evidence.claim_id,
        evidence.source_type,
        evidence.source_url,
        evidence.paper_id,
        evidence.section,
        evidence.quote,
        evidence.normalized_text,
        evidence.confidence,
        evidence.verification_status,
        _datetime_to_iso_utc(evidence.created_at),
    )


def _row_to_evidence(row: tuple) -> Evidence:
    return Evidence(
        id=row[0],
        claim_id=row[1],
        source_type=row[2],
        source_url=row[3],
        paper_id=row[4],
        section=row[5],
        quote=row[6],
        normalized_text=row[7],
        confidence=row[8],
        verification_status=row[9],
        created_at=datetime.fromisoformat(row[10]),
    )


def _checkpoint_to_row(checkpoint: ReviewCheckpoint) -> tuple[object, ...]:
    return (
        checkpoint.id,
        checkpoint.task_id,
        checkpoint.project_id,
        checkpoint.checkpoint_type.value,
        checkpoint.title,
        json.dumps(checkpoint.content, ensure_ascii=False, default=str),
        checkpoint.status.value,
        checkpoint.decision.value if checkpoint.decision else None,
        checkpoint.comment,
        _datetime_to_iso_utc(checkpoint.created_at),
        _datetime_to_iso_utc(checkpoint.decided_at) if checkpoint.decided_at else None,
    )


def _row_to_checkpoint(row: tuple) -> ReviewCheckpoint:
    return ReviewCheckpoint(
        id=row[0],
        task_id=row[1],
        project_id=row[2],
        checkpoint_type=CheckpointType(row[3]),
        title=row[4],
        content=json.loads(row[5]),
        status=CheckpointStatus(row[6]),
        decision=ReviewDecision(row[7]) if row[7] else None,
        comment=row[8],
        created_at=datetime.fromisoformat(row[9]),
        decided_at=datetime.fromisoformat(row[10]) if row[10] else None,
    )


class ResearchSQLiteRepository(ResearchRepository):
    """Stores Research OS domain models in the shared SQLite database.

    Created by `SQLiteStore.research_repository()` with the store's own
    connection and lock, so it never opens a second database connection.
    """

    def __init__(self, conn: aiosqlite.Connection, lock: asyncio.Lock) -> None:
        self._conn = conn
        self._lock = lock

    async def create_project(self, project: ResearchProject) -> None:
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO research_projects({_PROJECT_COLUMNS}) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _project_to_row(project),
            )
            await self._conn.commit()

    async def upsert_project(self, project: ResearchProject) -> None:
        async with self._lock:
            await self._conn.execute(
                f"""
                INSERT INTO research_projects({_PROJECT_COLUMNS})
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    research_question = excluded.research_question,
                    field = excluded.field,
                    constraints_json = excluded.constraints_json,
                    target_venue = excluded.target_venue,
                    status = excluded.status,
                    owner = excluded.owner,
                    updated_at = excluded.updated_at
                """,
                _project_to_row(project),
            )
            await self._conn.commit()

    async def get_project(self, project_id: str) -> ResearchProject | None:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_PROJECT_COLUMNS} FROM research_projects WHERE id = ?",
                (project_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _row_to_project(row) if row else None

    async def list_projects(self, limit: int = 50) -> list[ResearchProject]:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_PROJECT_COLUMNS} FROM research_projects "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_project(row) for row in rows]

    async def create_paper(self, paper: Paper) -> None:
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO papers({_PAPER_COLUMNS}) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _paper_to_row(paper),
            )
            await self._conn.commit()

    async def upsert_paper(self, paper: Paper) -> None:
        async with self._lock:
            await self._conn.execute(
                f"""
                INSERT INTO papers({_PAPER_COLUMNS})
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id = excluded.project_id,
                    title = excluded.title,
                    authors_json = excluded.authors_json,
                    year = excluded.year,
                    venue = excluded.venue,
                    abstract = excluded.abstract,
                    url = excluded.url,
                    pdf_url = excluded.pdf_url,
                    arxiv_id = excluded.arxiv_id,
                    doi = excluded.doi,
                    semantic_scholar_id = excluded.semantic_scholar_id,
                    citation_count = excluded.citation_count,
                    code_url = excluded.code_url,
                    dataset_mentions_json = excluded.dataset_mentions_json,
                    screening_status = excluded.screening_status,
                    relevance_score = excluded.relevance_score,
                    created_at = excluded.created_at
                """,
                _paper_to_row(paper),
            )
            await self._conn.commit()

    async def get_paper(self, paper_id: str) -> Paper | None:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_PAPER_COLUMNS} FROM papers WHERE id = ?",
                (paper_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _row_to_paper(row) if row else None

    async def list_project_papers(
        self,
        project_id: str,
        *,
        limit: int = 100,
        screening_status: PaperScreeningStatus | None = None,
    ) -> list[Paper]:
        if screening_status is None:
            sql = f"SELECT {_PAPER_COLUMNS} FROM papers WHERE project_id = ? "
            params: tuple[object, ...] = (project_id, limit)
        else:
            sql = (
                f"SELECT {_PAPER_COLUMNS} FROM papers WHERE project_id = ? "
                "AND screening_status = ? "
            )
            params = (project_id, screening_status.value, limit)
        async with self._lock:
            cursor = await self._conn.execute(
                sql + "ORDER BY created_at DESC LIMIT ?",
                params,
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_paper(row) for row in rows]

    async def create_paper_note(self, note: PaperNote) -> None:
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO paper_notes({_PAPER_NOTE_COLUMNS}) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _paper_note_to_row(note),
            )
            await self._conn.commit()

    async def upsert_paper_note(self, note: PaperNote) -> None:
        async with self._lock:
            await self._conn.execute(
                f"""
                INSERT INTO paper_notes({_PAPER_NOTE_COLUMNS})
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    paper_id = excluded.paper_id,
                    problem = excluded.problem,
                    method = excluded.method,
                    training_setup = excluded.training_setup,
                    datasets_json = excluded.datasets_json,
                    metrics_json = excluded.metrics_json,
                    baselines_json = excluded.baselines_json,
                    main_results = excluded.main_results,
                    limitations = excluded.limitations,
                    reproducibility_notes = excluded.reproducibility_notes,
                    important_sections_json = excluded.important_sections_json,
                    created_at = excluded.created_at
                """,
                _paper_note_to_row(note),
            )
            await self._conn.commit()

    async def get_paper_note(self, note_id: str) -> PaperNote | None:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_PAPER_NOTE_COLUMNS} FROM paper_notes WHERE id = ?",
                (note_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _row_to_paper_note(row) if row else None

    async def list_paper_notes(self, paper_id: str) -> list[PaperNote]:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_PAPER_NOTE_COLUMNS} FROM paper_notes WHERE paper_id = ? "
                "ORDER BY created_at DESC",
                (paper_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_paper_note(row) for row in rows]

    async def record_tool_call(self, call: ToolCallRecord) -> None:
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO tool_calls({_TOOL_CALL_COLUMNS}) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _tool_call_to_row(call),
            )
            await self._conn.commit()

    async def record_tool_observation(self, observation: ToolObservationRecord) -> None:
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO tool_observations({_TOOL_OBSERVATION_COLUMNS}) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                _tool_observation_to_row(observation),
            )
            await self._conn.commit()

    async def list_tool_calls(self, task_id: str) -> list[ToolCallRecord]:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_TOOL_CALL_COLUMNS} FROM tool_calls WHERE task_id = ? "
                "ORDER BY created_at ASC",
                (task_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_tool_call(row) for row in rows]

    async def list_project_tool_calls(self, project_id: str) -> list[ToolCallRecord]:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_TOOL_CALL_COLUMNS} FROM tool_calls WHERE project_id = ? "
                "ORDER BY created_at ASC",
                (project_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_tool_call(row) for row in rows]

    async def list_tool_observations(self, tool_call_id: str) -> list[ToolObservationRecord]:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_TOOL_OBSERVATION_COLUMNS} FROM tool_observations "
                "WHERE tool_call_id = ? ORDER BY created_at ASC",
                (tool_call_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_tool_observation(row) for row in rows]

    async def list_tool_observations_for_calls(
        self,
        tool_call_ids: list[str],
    ) -> dict[str, list[ToolObservationRecord]]:
        if not tool_call_ids:
            return {}
        placeholders = ", ".join("?" for _ in tool_call_ids)
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_TOOL_OBSERVATION_COLUMNS} FROM tool_observations "
                f"WHERE tool_call_id IN ({placeholders}) "
                "ORDER BY tool_call_id ASC, created_at ASC",
                tuple(tool_call_ids),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        grouped: dict[str, list[ToolObservationRecord]] = {call_id: [] for call_id in tool_call_ids}
        for row in rows:
            observation = _row_to_tool_observation(row)
            grouped.setdefault(observation.tool_call_id, []).append(observation)
        return grouped

    # --- claims ----------------------------------------------------------

    async def create_claim(self, claim: Claim) -> None:
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO claims({_CLAIM_COLUMNS}) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _claim_to_row(claim),
            )
            await self._conn.commit()

    async def upsert_claim(self, claim: Claim) -> None:
        async with self._lock:
            await self._conn.execute(
                f"""
                INSERT INTO claims({_CLAIM_COLUMNS})
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id = excluded.project_id,
                    text = excluded.text,
                    claim_type = excluded.claim_type,
                    paper_id = excluded.paper_id,
                    section = excluded.section,
                    confidence = excluded.confidence,
                    evidence_ids_json = excluded.evidence_ids_json,
                    status = excluded.status
                """,
                _claim_to_row(claim),
            )
            await self._conn.commit()

    async def get_claim(self, claim_id: str) -> Claim | None:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_CLAIM_COLUMNS} FROM claims WHERE id = ?",
                (claim_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _row_to_claim(row) if row else None

    async def list_project_claims(self, project_id: str, *, limit: int = 500) -> list[Claim]:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_CLAIM_COLUMNS} FROM claims WHERE project_id = ? "
                "ORDER BY created_at ASC LIMIT ?",
                (project_id, limit),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_claim(row) for row in rows]

    async def list_paper_claims(self, paper_id: str) -> list[Claim]:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_CLAIM_COLUMNS} FROM claims WHERE paper_id = ? "
                "ORDER BY created_at ASC",
                (paper_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_claim(row) for row in rows]

    # --- evidence --------------------------------------------------------

    async def create_evidence(self, evidence: Evidence) -> None:
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO evidence({_EVIDENCE_COLUMNS}) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _evidence_to_row(evidence),
            )
            await self._conn.commit()

    async def get_evidence(self, evidence_id: str) -> Evidence | None:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_EVIDENCE_COLUMNS} FROM evidence WHERE id = ?",
                (evidence_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _row_to_evidence(row) if row else None

    async def list_claim_evidence(self, claim_id: str) -> list[Evidence]:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_EVIDENCE_COLUMNS} FROM evidence WHERE claim_id = ? "
                "ORDER BY created_at ASC",
                (claim_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_evidence(row) for row in rows]

    async def list_project_evidence(self, project_id: str) -> list[Evidence]:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_prefixed(_EVIDENCE_COLUMNS, 'evidence')} FROM evidence "
                "JOIN claims ON evidence.claim_id = claims.id "
                "WHERE claims.project_id = ? "
                "ORDER BY evidence.created_at ASC",
                (project_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_evidence(row) for row in rows]

    # --- review checkpoints ---------------------------------------------

    async def create_checkpoint(self, checkpoint: ReviewCheckpoint) -> None:
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO review_checkpoints({_CHECKPOINT_COLUMNS}) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _checkpoint_to_row(checkpoint),
            )
            await self._conn.commit()

    async def upsert_checkpoint(self, checkpoint: ReviewCheckpoint) -> None:
        async with self._lock:
            await self._conn.execute(
                f"""
                INSERT INTO review_checkpoints({_CHECKPOINT_COLUMNS})
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_id = excluded.task_id,
                    project_id = excluded.project_id,
                    checkpoint_type = excluded.checkpoint_type,
                    title = excluded.title,
                    content_json = excluded.content_json,
                    status = excluded.status,
                    decision = excluded.decision,
                    comment = excluded.comment,
                    decided_at = excluded.decided_at
                """,
                _checkpoint_to_row(checkpoint),
            )
            await self._conn.commit()

    async def get_checkpoint(self, checkpoint_id: str) -> ReviewCheckpoint | None:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_CHECKPOINT_COLUMNS} FROM review_checkpoints WHERE id = ?",
                (checkpoint_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _row_to_checkpoint(row) if row else None

    async def list_project_checkpoints(self, project_id: str) -> list[ReviewCheckpoint]:
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT {_CHECKPOINT_COLUMNS} FROM review_checkpoints WHERE project_id = ? "
                "ORDER BY created_at ASC",
                (project_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_checkpoint(row) for row in rows]

    # --- research events -------------------------------------------------

    async def record_research_event(self, event: ResearchEvent) -> None:
        payload = event.model_dump(mode="json")
        row = (
            _id("evt"),
            event.task_id,
            event.project_id,
            event.seq,
            event.type,
            json.dumps(payload, ensure_ascii=False, default=str),
            _datetime_to_iso_utc(event.timestamp),
            _datetime_to_iso_utc(utcnow()),
        )
        async with self._lock:
            await self._conn.execute(
                f"INSERT INTO research_events({_RESEARCH_EVENT_COLUMNS}) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
            await self._conn.commit()

    async def list_research_events(self, task_id: str) -> list[dict]:
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT payload_json FROM research_events WHERE task_id = ? "
                "ORDER BY seq ASC, created_at ASC",
                (task_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [json.loads(row[0]) for row in rows]
