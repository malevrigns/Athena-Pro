from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class VisualActionType(str, Enum):
    READ = 'read'
    CLICK = 'click'
    TYPE = 'type'
    SCROLL = 'scroll'
    DOWNLOAD = 'download'
    SUBMIT = 'submit'


class VisualAction(BaseModel):
    action_type: VisualActionType
    selector_hint: str = ''
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    text: str = ''
    screenshot_id: str = ''
    risk_reason: str = ''

    def requires_approval(self) -> bool:
        return self.action_type in {VisualActionType.CLICK, VisualActionType.TYPE, VisualActionType.DOWNLOAD, VisualActionType.SUBMIT}

    def redacted_text(self) -> str:
        if not self.text:
            return ''
        if len(self.text) <= 4:
            return '••••'
        return self.text[:2] + '••••' + self.text[-2:]

    def human_summary(self) -> str:
        target = self.selector_hint or f'({self.x}, {self.y})'
        if self.action_type == VisualActionType.TYPE:
            return f'type into {target}: {self.redacted_text()}'
        return f'{self.action_type.value} {target}'
