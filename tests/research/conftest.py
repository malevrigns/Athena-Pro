"""Shared fixtures for Research OS tests."""

from __future__ import annotations

import asyncio

import pytest

from athena.persistence.sqlite_store import SQLiteStore


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
