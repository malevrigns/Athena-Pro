from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from athena.computer.actions import VisualAction, VisualActionType
from athena.schemas import RiskLevel


@dataclass
class VisualDecision:
    action: str
    risk: RiskLevel
    verdict: str
    reason: str


class VisualPolicy:
    deny_domains = {'bank.example', 'payments.example'}
    dangerous_words = {'delete', 'transfer', 'send', 'purchase', '提交', '付款', '删除'}

    def classify(self, action: VisualAction, current_url: str = '') -> VisualDecision:
        domain = urlparse(current_url).netloc
        if domain in self.deny_domains:
            return VisualDecision(action.human_summary(), RiskLevel.CRITICAL, 'deny', 'sensitive domain')
        text = (action.selector_hint + ' ' + action.text).lower()
        if any(word.lower() in text for word in self.dangerous_words):
            return VisualDecision(action.human_summary(), RiskLevel.CRITICAL, 'ask', 'dangerous wording')
        if action.action_type == VisualActionType.READ:
            return VisualDecision(action.human_summary(), RiskLevel.LOW, 'allow', 'read-only screenshot')
        if action.action_type == VisualActionType.SCROLL:
            return VisualDecision(action.human_summary(), RiskLevel.LOW, 'allow', 'navigation only')
        if action.action_type in {VisualActionType.CLICK, VisualActionType.TYPE}:
            return VisualDecision(action.human_summary(), RiskLevel.HIGH, 'ask', 'state-changing visual action')
        return VisualDecision(action.human_summary(), RiskLevel.MEDIUM, 'ask', 'unknown visual action')
