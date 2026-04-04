from __future__ import annotations

import asyncio
from unittest import IsolatedAsyncioTestCase

from job_hunter_agent.app import JobHunterApplication


class _FakeRuntimeGuard:
    def prepare_for_startup(self) -> list[int]:
        return []

    def release(self) -> None:
        return None


class _FakeRepository:
    def interrupt_running_collection_runs(self) -> int:
        return 0


class _FakeNotifier:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


class _FakeSettings:
    def __init__(self, review_polling_grace_seconds: int) -> None:
        self.review_polling_grace_seconds = review_polling_grace_seconds


class JobHunterApplicationRunTests(IsolatedAsyncioTestCase):
    async def test_run_once_waits_for_review_window_when_jobs_were_sent(self) -> None:
        app = JobHunterApplication.__new__(JobHunterApplication)
        app.enable_telegram = True
        app.settings = _FakeSettings(review_polling_grace_seconds=42)
        app.repository = _FakeRepository()
        app.runtime_guard = _FakeRuntimeGuard()
        app.notifier = _FakeNotifier()

        async def fake_run_collection_cycle() -> bool:
            return True

        app.run_collection_cycle = fake_run_collection_cycle

        waited: list[int] = []
        original_sleep = asyncio.sleep

        async def fake_sleep(seconds: float) -> None:
            waited.append(int(seconds))

        try:
            asyncio.sleep = fake_sleep
            await app.run(run_once=True)
        finally:
            asyncio.sleep = original_sleep

        self.assertEqual(waited, [42])
        self.assertTrue(app.notifier.started)
        self.assertTrue(app.notifier.stopped)

    async def test_run_once_skips_review_window_without_jobs(self) -> None:
        app = JobHunterApplication.__new__(JobHunterApplication)
        app.enable_telegram = True
        app.settings = _FakeSettings(review_polling_grace_seconds=42)
        app.repository = _FakeRepository()
        app.runtime_guard = _FakeRuntimeGuard()
        app.notifier = _FakeNotifier()

        async def fake_run_collection_cycle() -> bool:
            return False

        app.run_collection_cycle = fake_run_collection_cycle

        waited: list[int] = []
        original_sleep = asyncio.sleep

        async def fake_sleep(seconds: float) -> None:
            waited.append(int(seconds))

        try:
            asyncio.sleep = fake_sleep
            await app.run(run_once=True)
        finally:
            asyncio.sleep = original_sleep

        self.assertEqual(waited, [])
        self.assertTrue(app.notifier.started)
        self.assertTrue(app.notifier.stopped)
