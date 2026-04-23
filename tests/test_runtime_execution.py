from __future__ import annotations

import asyncio
from unittest import IsolatedAsyncioTestCase

from job_hunter_agent.application.runtime_execution import run_collection_cycle, run_fixed_cycles
from job_hunter_agent.core.domain import CollectionReport, JobPosting


class _FakeLogger:
    def info(self, *args, **kwargs) -> None:
        return None

    def exception(self, *args, **kwargs) -> None:
        return None


class _FakeRun:
    def __init__(self, run_id: int = 1) -> None:
        self.id = run_id


class _FakeRepository:
    def __init__(self) -> None:
        self.finished: list[tuple[int, str, int, int, int]] = []

    def start_collection_run(self):
        return _FakeRun(7)

    def finish_collection_run(self, run_id: int, *, status: str, jobs_seen: int, jobs_saved: int, errors: int) -> None:
        self.finished.append((run_id, status, jobs_seen, jobs_saved, errors))


class _FakeCollector:
    def __init__(self, report: CollectionReport | None = None, *, should_fail: bool = False) -> None:
        self.report = report
        self.should_fail = should_fail

    async def collect_new_jobs_report(self) -> CollectionReport:
        if self.should_fail:
            raise RuntimeError("falha collector")
        assert self.report is not None
        return self.report


class _FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.review_payloads: list[list[JobPosting]] = []

    async def send_text(self, text: str) -> None:
        self.messages.append(text)

    async def notify_jobs_for_review(self, jobs: list[JobPosting]) -> None:
        self.review_payloads.append(jobs)


class RunFixedCyclesAdaptivePollingTests(IsolatedAsyncioTestCase):
    async def test_run_fixed_cycles_applies_adaptive_backoff_with_cap(self) -> None:
        cycle_outcomes = iter([False, False, False, False])

        async def fake_run_collection_cycle() -> bool:
            return next(cycle_outcomes)

        wait_calls: list[int] = []

        async def fake_wait_for_review_window() -> None:
            wait_calls.append(1)

        slept: list[int] = []
        original_sleep = asyncio.sleep

        async def fake_sleep(seconds: float) -> None:
            slept.append(int(seconds))

        try:
            asyncio.sleep = fake_sleep
            await run_fixed_cycles(
                cycles=4,
                interval_seconds=10,
                run_collection_cycle=fake_run_collection_cycle,
                wait_for_review_window=fake_wait_for_review_window,
                adaptive_backoff_enabled=True,
                empty_cycles_before_backoff=2,
                backoff_multiplier=2.0,
                backoff_max_interval_seconds=35,
                logger=_FakeLogger(),
            )
        finally:
            asyncio.sleep = original_sleep

        self.assertEqual(wait_calls, [])
        self.assertEqual(slept, [10, 20, 35])

    async def test_run_fixed_cycles_resets_backoff_after_cycle_with_jobs(self) -> None:
        cycle_outcomes = iter([False, False, True, False])

        async def fake_run_collection_cycle() -> bool:
            return next(cycle_outcomes)

        wait_calls: list[int] = []

        async def fake_wait_for_review_window() -> None:
            wait_calls.append(1)

        slept: list[int] = []
        original_sleep = asyncio.sleep

        async def fake_sleep(seconds: float) -> None:
            slept.append(int(seconds))

        try:
            asyncio.sleep = fake_sleep
            await run_fixed_cycles(
                cycles=4,
                interval_seconds=10,
                run_collection_cycle=fake_run_collection_cycle,
                wait_for_review_window=fake_wait_for_review_window,
                adaptive_backoff_enabled=True,
                empty_cycles_before_backoff=2,
                backoff_multiplier=2.0,
                backoff_max_interval_seconds=40,
                logger=_FakeLogger(),
            )
        finally:
            asyncio.sleep = original_sleep

        self.assertEqual(wait_calls, [1])
        self.assertEqual(slept, [10, 20, 10])


class RunCollectionCycleOrchestrationTests(IsolatedAsyncioTestCase):
    async def test_run_collection_cycle_notifies_review_when_jobs_exist(self) -> None:
        job = JobPosting(
            id=1,
            title="Backend Java",
            company="ACME",
            location="Brasil",
            work_mode="remoto",
            salary_text="Nao informado",
            url="https://example.com/job-1",
            source_site="LinkedIn",
            summary="Resumo",
            relevance=9,
            rationale="fit",
            external_key="key-1",
        )
        report = CollectionReport(jobs=(job,), jobs_seen=1, jobs_saved=1, errors=0)
        repository = _FakeRepository()
        notifier = _FakeNotifier()

        sent = await run_collection_cycle(
            repository,
            _FakeCollector(report),
            notifier,
            logger=_FakeLogger(),
        )

        self.assertTrue(sent)
        self.assertEqual(repository.finished, [(7, "success", 1, 1, 0)])
        self.assertEqual(len(notifier.review_payloads), 1)
        self.assertEqual(notifier.messages, [])

    async def test_run_collection_cycle_notifies_empty_when_no_jobs(self) -> None:
        report = CollectionReport(jobs=(), jobs_seen=3, jobs_saved=0, errors=0)
        repository = _FakeRepository()
        notifier = _FakeNotifier()

        sent = await run_collection_cycle(
            repository,
            _FakeCollector(report),
            notifier,
            logger=_FakeLogger(),
        )

        self.assertFalse(sent)
        self.assertEqual(repository.finished, [(7, "success", 3, 0, 0)])
        self.assertEqual(notifier.review_payloads, [])
        self.assertEqual(notifier.messages, ["Nenhuma vaga nova passou na triagem de hoje."])

    async def test_run_collection_cycle_notifies_failure_when_collector_raises(self) -> None:
        repository = _FakeRepository()
        notifier = _FakeNotifier()

        sent = await run_collection_cycle(
            repository,
            _FakeCollector(should_fail=True),
            notifier,
            logger=_FakeLogger(),
        )

        self.assertFalse(sent)
        self.assertEqual(repository.finished, [(7, "error", 0, 0, 1)])
        self.assertEqual(notifier.review_payloads, [])
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("Falha no ciclo de coleta", notifier.messages[0])
