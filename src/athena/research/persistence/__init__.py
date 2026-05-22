"""Research OS persistence layer.

Phase 1 step 2: durable SQLite storage for Research OS domain assets. The
SQLite repository reuses the existing `SQLiteStore` connection rather than
opening its own database.
"""

from __future__ import annotations

from .repository import ResearchRepository
from .sqlite_repository import RESEARCH_OS_SCHEMA, ResearchSQLiteRepository

__all__ = [
    "RESEARCH_OS_SCHEMA",
    "ResearchRepository",
    "ResearchSQLiteRepository",
]
