"""Server-global runtime settings — currently the citation-verification config.

Persisted in SQLite (see `athena.app_settings`) so changes survive restarts and
do not require editing `.env`.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from athena.app_settings import (
    CitationSettings,
    VerifierConfig,
    load_citation_settings,
    save_citation_settings,
)
from athena.llm_factory import build_verifier_llm

router = APIRouter(prefix="/v1/settings", tags=["settings"])


class VerifierOut(BaseModel):
    provider: str
    model: str
    base_url: str
    has_api_key: bool


class CitationSettingsOut(BaseModel):
    manual_review: bool
    verifier: VerifierOut


class VerifierIn(BaseModel):
    provider: str = "mock"
    model: str = ""
    base_url: str = ""
    # Empty / omitted => keep the stored key, so the UI never re-enters it.
    api_key: str | None = None


class CitationSettingsIn(BaseModel):
    manual_review: bool = True
    verifier: VerifierIn = Field(default_factory=VerifierIn)


def _to_out(s: CitationSettings) -> CitationSettingsOut:
    return CitationSettingsOut(
        manual_review=s.manual_review,
        verifier=VerifierOut(
            provider=s.verifier.provider,
            model=s.verifier.model,
            base_url=s.verifier.base_url,
            has_api_key=bool(s.verifier.api_key),
        ),
    )


@router.get("", response_model=CitationSettingsOut)
async def get_citation_settings():
    return _to_out(await load_citation_settings())


@router.put("", response_model=CitationSettingsOut)
async def update_citation_settings(body: CitationSettingsIn):
    current = await load_citation_settings()
    api_key = body.verifier.api_key
    if not api_key:  # blank => preserve the existing key
        api_key = current.verifier.api_key
    updated = CitationSettings(
        manual_review=body.manual_review,
        verifier=VerifierConfig(
            provider=(body.verifier.provider or "mock").strip().lower(),
            model=body.verifier.model.strip(),
            api_key=api_key,
            base_url=body.verifier.base_url.strip(),
        ),
    )
    await save_citation_settings(updated)
    return _to_out(updated)


@router.post("/verifier/test")
async def test_verifier():
    """Smoke-test the configured second model with a one-line probe."""
    verifier = (await load_citation_settings()).verifier
    llm = build_verifier_llm(verifier.provider, verifier.model, verifier.api_key, verifier.base_url)
    try:
        res = await llm.complete_full("请只回复两个字:正常。", node="citation_review")
        return {
            "ok": True,
            "model": getattr(res, "model", "") or verifier.model,
            "sample": (res.text or "").strip()[:80],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": str(exc)}
