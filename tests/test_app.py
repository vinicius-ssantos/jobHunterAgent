from __future__ import annotations

import asyncio
from unittest.mock import patch
from unittest import IsolatedAsyncioTestCase

from job_hunter_agent.app import JobHunterApplication, parse_args
from job_hunter_agent.domain import JobPosting


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


def _sample_job(*, job_id: int, status: str) -> JobPosting:
    return JobPosting(
        id=job_id,
        title="Backend Java",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url=f"https://example.com/{job_id}",
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia",
        external_key=f"key-{job_id}",
        status=status,
    )


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

    async def test_handle_approved_jobs_creates_application_drafts_only_for_approved(self) -> None:
        class _RepositoryWithJobs:
            def __init__(self) -> None:
                self.jobs = {
                    1: _sample_job(job_id=1, status="approved"),
                    2: _sample_job(job_id=2, status="collected"),
                }
                self.created: list[int] = []

            def get_job(self, job_id: int):
                return self.jobs.get(job_id)

            def create_application_draft(
                self,
                job_id: int,
                notes: str = "",
                *,
                support_level: str = "manual_review",
                support_rationale: str = "",
            ):
                self.created.append(job_id)
                return type(
                    "Draft",
                    (),
                    {
                        "job_id": job_id,
                        "notes": notes,
                        "support_level": support_level,
                        "support_rationale": support_rationale,
                    },
                )

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _RepositoryWithJobs()

        from job_hunter_agent.applicant import ApplicationPreparationService

        app.application_preparation = ApplicationPreparationService(app.repository)

        await app.handle_approved_jobs([1, 2, 999])

        self.assertEqual(app.repository.created, [1])

    async def test_handle_application_preflight_returns_service_message(self) -> None:
        class _PreflightService:
            def __init__(self) -> None:
                self.called_with: list[int] = []

            def run_for_application(self, application_id: int):
                self.called_with.append(application_id)
                return type(
                    "Result",
                    (),
                    {
                        "outcome": "ready",
                        "detail": "preflight ok",
                        "application_status": "confirmed",
                    },
                )

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.application_preflight = _PreflightService()

        reply = await app.handle_application_preflight(42)

        self.assertEqual(app.application_preflight.called_with, [42])
        self.assertEqual(reply, "Preflight: preflight ok (status=confirmed)")

    async def test_run_fixed_cycles_executes_requested_amount(self) -> None:
        app = JobHunterApplication.__new__(JobHunterApplication)
        app.enable_telegram = True
        app.settings = _FakeSettings(review_polling_grace_seconds=5)

        runs: list[int] = []

        async def fake_run_collection_cycle() -> bool:
            runs.append(1)
            return True

        waits: list[int] = []

        async def fake_wait_for_review_window() -> None:
            waits.append(1)

        app.run_collection_cycle = fake_run_collection_cycle
        app.wait_for_review_window = fake_wait_for_review_window

        await app.run_fixed_cycles(3)

        self.assertEqual(len(runs), 3)
        self.assertEqual(len(waits), 3)

    async def test_run_prefers_fixed_cycles_over_scheduler(self) -> None:
        app = JobHunterApplication.__new__(JobHunterApplication)
        app.enable_telegram = True
        app.settings = _FakeSettings(review_polling_grace_seconds=42)
        app.repository = _FakeRepository()
        app.runtime_guard = _FakeRuntimeGuard()
        app.notifier = _FakeNotifier()

        called: list[tuple[int, int]] = []

        async def fake_run_fixed_cycles(cycles: int, interval_seconds: int = 0) -> None:
            called.append((cycles, interval_seconds))

        async def fake_run_scheduler() -> None:
            raise AssertionError("scheduler should not run")

        app.run_fixed_cycles = fake_run_fixed_cycles
        app.run_scheduler = fake_run_scheduler

        await app.run(run_once=False, fixed_cycles=2, cycle_interval_seconds=15)

        self.assertEqual(called, [(2, 15)])
        self.assertTrue(app.notifier.started)
        self.assertTrue(app.notifier.stopped)


class ParseArgsTests(IsolatedAsyncioTestCase):
    async def test_parse_args_accepts_fixed_cycles(self) -> None:
        with patch("sys.argv", ["main.py", "--ciclos", "3", "--intervalo-ciclos-segundos", "10"]):
            args = parse_args()

        self.assertEqual(args.ciclos, 3)
        self.assertEqual(args.intervalo_ciclos_segundos, 10)
        self.assertFalse(args.agora)
