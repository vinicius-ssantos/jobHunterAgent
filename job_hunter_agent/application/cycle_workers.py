from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from job_hunter_agent.core.domain import CollectionReport, JobPosting


@dataclass(frozen=True)
class JobCollectedV1:
    run_id: int
    jobs: tuple[JobPosting, ...]
    jobs_seen: int
    jobs_saved: int
    errors: int


@dataclass(frozen=True)
class JobNormalizedV1:
    run_id: int
    external_key: str
    source_site: str


@dataclass(frozen=True)
class JobScoredV1:
    run_id: int
    external_key: str
    accepted: bool
    relevance: int


@dataclass(frozen=True)
class ApplicationActionRequestedV1:
    application_id: int
    action: str


@dataclass(frozen=True)
class ApplicationActionResultV1:
    application_id: int
    action: str
    outcome: str
    detail: str


class LocalEventQueue:
    def __init__(self) -> None:
        self._job_collected_events: list[JobCollectedV1] = []

    def publish_job_collected(self, event: JobCollectedV1) -> None:
        self._job_collected_events.append(event)

    def drain_job_collected(self) -> tuple[JobCollectedV1, ...]:
        drained = tuple(self._job_collected_events)
        self._job_collected_events.clear()
        return drained


class CollectionWorker(Protocol):
    async def collect(self) -> CollectionReport:
        raise NotImplementedError


class ReviewWorker(Protocol):
    async def notify_collection_failure(self, exc: Exception) -> None:
        raise NotImplementedError

    async def dispatch_jobs_for_review(self, event: JobCollectedV1) -> bool:
        raise NotImplementedError


class DefaultCollectionWorker:
    def __init__(self, collector) -> None:
        self.collector = collector

    async def collect(self) -> CollectionReport:
        return await self.collector.collect_new_jobs_report()


class DefaultReviewWorker:
    def __init__(self, notifier) -> None:
        self.notifier = notifier

    async def notify_collection_failure(self, exc: Exception) -> None:
        await self.notifier.send_text(f"Falha no ciclo de coleta: {exc}")

    async def dispatch_jobs_for_review(self, event: JobCollectedV1) -> bool:
        jobs = list(event.jobs)
        if not jobs:
            await self.notifier.send_text("Nenhuma vaga nova passou na triagem de hoje.")
            return False
        await self.notifier.notify_jobs_for_review(jobs)
        return True


class CollectionCycleOrchestrator:
    def __init__(
        self,
        *,
        repository,
        collection_worker: CollectionWorker,
        review_worker: ReviewWorker,
        event_queue: LocalEventQueue | None = None,
    ) -> None:
        self.repository = repository
        self.collection_worker = collection_worker
        self.review_worker = review_worker
        self.event_queue = event_queue or LocalEventQueue()

    async def run_cycle(self, *, logger) -> bool:
        run = self.repository.start_collection_run()
        logger.info("Ciclo de coleta iniciado. run_id=%s", run.id)
        try:
            report = await self.collection_worker.collect()
            self.repository.finish_collection_run(
                run.id,
                status="success",
                jobs_seen=report.jobs_seen,
                jobs_saved=report.jobs_saved,
                errors=report.errors,
            )
        except Exception as exc:
            self.repository.finish_collection_run(
                run.id,
                status="error",
                jobs_seen=0,
                jobs_saved=0,
                errors=1,
            )
            logger.exception("Falha no ciclo de coleta.")
            await self.review_worker.notify_collection_failure(exc)
            return False

        event = JobCollectedV1(
            run_id=run.id,
            jobs=tuple(report.jobs),
            jobs_seen=report.jobs_seen,
            jobs_saved=report.jobs_saved,
            errors=report.errors,
        )
        self.event_queue.publish_job_collected(event)
        jobs_sent_for_review = False
        for collected_event in self.event_queue.drain_job_collected():
            if await self.review_worker.dispatch_jobs_for_review(collected_event):
                jobs_sent_for_review = True
        return jobs_sent_for_review
