from __future__ import annotations

from dataclasses import dataclass

from athena.schemas import Finding, QualityScore


@dataclass
class ClaimCheck:
    claim: str
    supported: bool
    source_count: int
    reason: str


class FactChecker:
    """Lightweight deterministic fact checker.

    The production version can call an LLM. The starter keeps a strict heuristic: every finding must
    have at least two independent sources and non-empty evidence.
    """

    def extract_claims(self, findings: list[Finding]) -> list[str]:
        claims: list[str] = []
        for finding in findings:
            claims.append(finding.summary)
            claims.extend(finding.evidence[:2])
        return claims

    def check(self, finding: Finding) -> ClaimCheck:
        source_count = len({s.url for s in finding.sources})
        supported = source_count >= 2 and bool(finding.evidence)
        reason = "source threshold satisfied" if supported else "insufficient independent sources"
        return ClaimCheck(finding.summary, supported, source_count, reason)

    def score(self, findings: list[Finding]) -> QualityScore:
        if not findings:
            return QualityScore(notes=["no findings"])
        checks = [self.check(f) for f in findings]
        factuality = sum(1 for c in checks if c.supported) / len(checks)
        coverage = min(1.0, len(findings) / 4)
        citation_integrity = min(1.0, sum(c.source_count for c in checks) / (len(checks) * 3))
        contradiction_risk = 0.1 if factuality > 0.7 else 0.4
        overall = round((factuality * 0.4 + coverage * 0.25 + citation_integrity * 0.25 + (1 - contradiction_risk) * 0.1), 3)
        return QualityScore(
            factuality=round(factuality, 3),
            coverage=round(coverage, 3),
            citation_integrity=round(citation_integrity, 3),
            contradiction_risk=contradiction_risk,
            overall=overall,
            notes=[c.reason for c in checks if not c.supported],
        )
