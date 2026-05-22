"""Server-global application settings persisted in SQLite.

Unlike `athena.config.Settings` (read once from `.env`), these settings are
mutable at runtime through the `/v1/settings` API and survive restarts. Today
this only holds the citation-verification configuration, but the `app_settings`
key/value table can carry any future runtime-tunable option.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from athena.persistence import get_store

_CITATION_KEY = "citation_settings"


class VerifierConfig(BaseModel):
    """An independently-configured second model used for citation review."""

    provider: str = "mock"          # mock | openai | anthropic | deepseek | openrouter | gemma
    model: str = ""
    api_key: str = ""
    base_url: str = ""


class CitationSettings(BaseModel):
    """How report citations get verified once a research task finishes."""

    # True  -> the user verifies each citation by hand (UI prompts them).
    # False -> the `verifier` model auto-decides pass / flag / reject.
    manual_review: bool = True
    verifier: VerifierConfig = Field(default_factory=VerifierConfig)


async def load_citation_settings() -> CitationSettings:
    """Read citation settings from SQLite, falling back to safe defaults."""
    raw = await get_store().get_app_setting(_CITATION_KEY)
    if not raw:
        return CitationSettings()
    try:
        return CitationSettings.model_validate_json(raw)
    except Exception:
        return CitationSettings()


async def save_citation_settings(settings: CitationSettings) -> CitationSettings:
    """Persist citation settings; returns the stored value for convenience."""
    await get_store().set_app_setting(_CITATION_KEY, settings.model_dump_json())
    return settings
