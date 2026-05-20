from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch

from athena.schemas import PermissionDecision, PermissionRequest, RiskLevel, Scope


@dataclass
class Rule:
    tool_pattern: str
    risk_level: RiskLevel
    default: str = "ask"  # allow | ask | deny
    reason: str = ""


DEFAULT_RULES = [
    Rule("web_search", RiskLevel.LOW, "allow", "read-only public search"),
    Rule("fetch_url", RiskLevel.LOW, "allow", "read-only fetch"),
    Rule("python_repl", RiskLevel.MEDIUM, "ask", "code execution requires review"),
    Rule("bash", RiskLevel.HIGH, "ask", "shell execution requires review"),
    Rule("computer.click", RiskLevel.HIGH, "ask", "visual action changes external UI"),
    Rule("computer.type", RiskLevel.CRITICAL, "ask", "typing into external UI can submit data"),
    Rule("delete_*", RiskLevel.CRITICAL, "deny", "destructive operations are blocked"),
]


@dataclass
class PermissionEngine:
    rules: list[Rule] = field(default_factory=lambda: list(DEFAULT_RULES))
    grants: dict[tuple[str, str], PermissionDecision] = field(default_factory=dict)

    def classify(self, tool_name: str) -> Rule:
        for rule in self.rules:
            if fnmatch(tool_name, rule.tool_pattern):
                return rule
        return Rule(tool_name, RiskLevel.MEDIUM, "ask", "unknown tool")

    def check(self, request: PermissionRequest, session_id: str = "default") -> str:
        grant = self.grants.get((session_id, request.tool_name))
        if grant and grant.approved and grant.scope in {Scope.SESSION, Scope.ALWAYS}:
            return "allow"
        rule = self.classify(request.tool_name)
        request.risk_level = rule.risk_level
        request.reason = request.reason or rule.reason
        return rule.default

    def record(self, decision: PermissionDecision, tool_name: str, session_id: str = "default") -> None:
        if decision.approved and decision.scope in {Scope.SESSION, Scope.ALWAYS}:
            self.grants[(session_id, tool_name)] = decision
