from __future__ import annotations

from dataclasses import dataclass

from athena.schemas import Finding, QualityScore


@dataclass
class ClaimCheck:
    claim: str
    supported: bool
    source_count: int
    credibility: float
    reason: str


class FactChecker:
    """Deterministic fact checker.

    A claim is judged not by raw source *count* alone, but by independent
    source count, the presence of traceable evidence, and the average
    credibility of those sources (internal verified knowledge scores higher
    than an anonymous web page). The production version can defer to an LLM.
    """

    def extract_claims(self, findings: list[Finding]) -> list[str]:
        claims: list[str] = []
        for finding in findings:
            claims.append(finding.summary)
            claims.extend(finding.evidence[:2])
        return claims

    def check(self, finding: Finding) -> ClaimCheck:
        distinct = {s.url: s for s in finding.sources if s.url}
        source_count = len(distinct)
        credibility = (
            sum(s.credibility for s in distinct.values()) / source_count
            if source_count else 0.0
        )
        has_evidence = bool(finding.evidence)
        supported = source_count >= 2 and has_evidence and credibility >= 0.45
        if supported:
            reason = "多来源交叉验证, 平均可信度达标"
        elif source_count < 2:
            reason = "独立来源不足 (<2)"
        elif not has_evidence:
            reason = "缺少可追溯的证据条目"
        else:
            reason = f"来源平均可信度偏低 ({credibility:.2f})"
        return ClaimCheck(finding.summary, supported, source_count, round(credibility, 3), reason)

    def score(self, findings: list[Finding]) -> QualityScore:
        if not findings:
            return QualityScore(notes=["no findings"])
        checks = [self.check(f) for f in findings]
        support_ratio = sum(1 for c in checks if c.supported) / len(checks)
        avg_credibility = sum(c.credibility for c in checks) / len(checks)
        # Factuality blends how many claims are supported with how credible
        # their sources are — not a pure pass/fail count.
        factuality = round(0.7 * support_ratio + 0.3 * avg_credibility, 3)
        coverage = round(min(1.0, len(findings) / 4), 3)
        raw_integrity = sum(c.source_count for c in checks) / (len(checks) * 3)
        # Citation integrity is discounted when sources are low-credibility.
        citation_integrity = round(min(1.0, raw_integrity) * (0.6 + 0.4 * avg_credibility), 3)
        contradiction_risk = 0.1 if factuality > 0.7 else 0.4
        overall = round(
            factuality * 0.4 + coverage * 0.25 + citation_integrity * 0.25 + (1 - contradiction_risk) * 0.1,
            3,
        )
        return QualityScore(
            factuality=factuality,
            coverage=coverage,
            citation_integrity=citation_integrity,
            contradiction_risk=contradiction_risk,
            overall=overall,
            notes=[c.reason for c in checks if not c.supported],
        )
