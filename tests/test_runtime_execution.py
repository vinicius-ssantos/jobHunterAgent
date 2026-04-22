from __future__ import annotations

import asyncio
from unittest import IsolatedAsyncioTestCase

from job_hunter_agent.application.runtime_execution import run_fixed_cycles


class _FakeLogger:
    def info(self, *args, **kwargs) -> None:
        return None


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
