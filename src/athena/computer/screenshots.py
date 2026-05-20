from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass
class Screenshot:
    id: str
    path: Path
    width: int
    height: int
    mime_type: str = 'image/png'

    def as_data_url(self) -> str:
        raw = self.path.read_bytes()
        return f'data:{self.mime_type};base64,' + base64.b64encode(raw).decode()


class ScreenshotStore:
    def __init__(self, root: Path | None = None):
        self.root = root or Path('.athena-data/screenshots')
        self.root.mkdir(parents=True, exist_ok=True)

    def save_png(self, data: bytes, width: int, height: int) -> Screenshot:
        shot_id = f'shot_{uuid4().hex[:10]}'
        path = self.root / f'{shot_id}.png'
        path.write_bytes(data)
        return Screenshot(id=shot_id, path=path, width=width, height=height)

    def get(self, shot_id: str) -> Screenshot | None:
        path = self.root / f'{shot_id}.png'
        if not path.exists():
            return None
        return Screenshot(id=shot_id, path=path, width=0, height=0)
