from __future__ import annotations

import json
from typing import AsyncIterator

from athena.schemas import StreamEvent


def encode_sse(event: StreamEvent) -> str:
    payload = json.dumps(event.model_dump(mode='json'), ensure_ascii=False, default=str)
    return f'data: {payload}\n\n'


async def stream_to_sse(events: AsyncIterator[StreamEvent]) -> AsyncIterator[str]:
    async for event in events:
        yield encode_sse(event)
