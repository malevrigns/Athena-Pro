"""Extract a real supporting quote from a source's page.

The Writer used to set a citation's `quote` to the raw search snippet. This
fetches the actual page and picks the passage most relevant to the claim it
grounds, falling back to the snippet on any failure (offline, mock URLs,
non-HTML, timeouts) so the pipeline never breaks on a bad source.
"""

from __future__ import annotations

import re

from athena.observability import logger
from athena.tools.web_fetch import fetch_url

_SENTENCE_SPLIT = re.compile(r"(?<=[。!?.!?])\s+|\n+")
_TERM = re.compile(r"[\w一-鿿]{2,}")


def _is_fetchable(url: str) -> bool:
    """Only real, external HTTP(S) URLs are worth a network round-trip."""
    u = (url or "").strip().lower()
    if not (u.startswith("http://") or u.startswith("https://")):
        return False
    # Placeholder hosts used by mock search / tests — never fetch these.
    return "example.com" not in u and "example.invalid" not in u


def _relevance(sentence: str, terms: list[str]) -> int:
    s = sentence.lower()
    return sum(1 for t in terms if t in s)


async def extract_quote(url: str, claim: str, fallback: str = "", *, max_len: int = 280) -> str:
    """Return a passage from the page at `url` most relevant to `claim`.

    `fallback` (typically the search snippet) is returned whenever the page
    cannot be fetched or contains nothing usable.
    """
    fallback = (fallback or "").strip()[:max_len]
    if not _is_fetchable(url):
        return fallback
    try:
        page = await fetch_url(url)
    except Exception as exc:  # noqa: BLE001
        logger.info("quote_extract.fetch_failed url=%s err=%s", url, exc)
        return fallback
    if page.status_code >= 400 or not page.text:
        return fallback

    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(page.text) if 30 <= len(s.strip()) <= 400]
    if not sentences:
        return page.text[:max_len].strip() or fallback

    terms = [t.lower() for t in _TERM.findall(claim or "")][:12]
    best = max(sentences, key=lambda s: _relevance(s, terms)) if terms else sentences[0]
    if terms and _relevance(best, terms) == 0:
        # Nothing matched the claim — the first substantial sentence of the
        # real article is still better grounding than a search snippet.
        best = sentences[0]
    return best[:max_len]
