from __future__ import annotations

from urllib.parse import urlparse

from athena.schemas import Finding, Source


def validate_source(source: Source) -> bool:
    # Internal knowledge-base sources are addressed by an in-app route
    # (e.g. /knowledge?item=...) rather than an external URL — accept them as
    # long as they carry a non-empty locator, so the quality gate keeps them
    # instead of silently dropping every internal citation.
    if source.source_type == "internal":
        return bool((source.url or "").strip())
    parsed = urlparse(source.url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_findings_sources(findings: list[Finding]) -> tuple[list[Finding], list[str]]:
    errors: list[str] = []
    for finding in findings:
        valid_sources = []
        for source in finding.sources:
            if validate_source(source):
                valid_sources.append(source)
            else:
                errors.append(f"invalid source url for {finding.id}: {source.url}")
        finding.sources = valid_sources
    return findings, errors
