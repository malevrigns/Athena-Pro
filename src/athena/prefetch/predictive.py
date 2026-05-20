from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from athena.prefetch.cache import prefetch_cache
from athena.schemas import ResearchTopic, Source
from athena.tools.search import SearchClient


@dataclass
class PrefetchJob:
    task_id: str
    topic_id: str
    query: str
    status: str = 'pending'
    sources: list[Source] = field(default_factory=list)
    error: str = ''


class PrefetchScheduler:
    """Fire-and-forget prefetch scheduler.

    Planner usually pauses for human review. This scheduler uses that idle window to warm search
    results. It is cancellable by task_id, so rejecting a plan does not leak background work.
    """

    def __init__(self, search: SearchClient | None = None):
        self.search = search or SearchClient()
        self._tasks: dict[str, list[asyncio.Task[None]]] = {}
        self._jobs: dict[str, PrefetchJob] = {}

    def start_for_plan(self, task_id: str, topics: list[ResearchTopic]) -> list[PrefetchJob]:
        jobs: list[PrefetchJob] = []
        for topic in topics:
            for query in topic.search_queries[:2] or [topic.question]:
                job = PrefetchJob(task_id=task_id, topic_id=topic.id, query=query)
                key = self._key(task_id, topic.id, query)
                self._jobs[key] = job
                task = asyncio.create_task(self._run(key, job), name=f'prefetch:{task_id}:{topic.id}')
                self._tasks.setdefault(task_id, []).append(task)
                jobs.append(job)
        return jobs

    async def _run(self, key: str, job: PrefetchJob) -> None:
        try:
            job.status = 'running'
            results = await self.search.web_search(job.query, max_results=4)
            job.sources = [result.to_source() for result in results]
            prefetch_cache.set(key, job.sources)
            job.status = 'done'
        except asyncio.CancelledError:
            job.status = 'cancelled'
            raise
        except Exception as exc:  # noqa: BLE001
            job.status = 'failed'
            job.error = str(exc)

    async def cancel(self, task_id: str) -> int:
        tasks = self._tasks.pop(task_id, [])
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return len(tasks)

    async def commit(self, task_id: str) -> None:
        self._tasks.pop(task_id, None)

    def lookup(self, task_id: str, topic: ResearchTopic) -> list[Source] | None:
        for query in topic.search_queries[:2] or [topic.question]:
            value = prefetch_cache.get(self._key(task_id, topic.id, query))
            if value:
                return list(value)  # type: ignore[arg-type]
        return None

    def jobs_for_task(self, task_id: str) -> list[PrefetchJob]:
        return [job for job in self._jobs.values() if job.task_id == task_id]

    @staticmethod
    def _key(task_id: str, topic_id: str, query: str) -> str:
        return f'{task_id}:{topic_id}:{query}'
