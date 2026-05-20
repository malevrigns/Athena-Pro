from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

from athena.schemas import Finding, ResearchTopic

SubagentFn = Callable[[ResearchTopic], Awaitable[Finding]]


@dataclass
class SubagentSpec:
    name: str
    description: str
    skills: list[str]
    runner: SubagentFn | None = None


@dataclass
class SubagentRegistry:
    agents: dict[str, SubagentSpec] = field(default_factory=dict)

    def register(self, spec: SubagentSpec) -> None:
        self.agents[spec.name] = spec

    def choose(self, topic: ResearchTopic) -> SubagentSpec | None:
        text = (topic.title + ' ' + topic.question).lower()
        for spec in self.agents.values():
            if any(skill.lower() in text for skill in spec.skills):
                return spec
        return next(iter(self.agents.values()), None) if self.agents else None

    def list_specs(self) -> list[dict[str, object]]:
        return [{'name': a.name, 'description': a.description, 'skills': a.skills} for a in self.agents.values()]
