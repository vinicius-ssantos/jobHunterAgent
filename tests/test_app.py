from __future__ import annotations

import asyncio
from unittest.mock import patch
from unittest import IsolatedAsyncioTestCase

from job_hunter_agent.app import JobHunterApplication, parse_args
from job_hunter_agent.composition import (
    build_known_job_lookup,
    create_linkedin_modal_interpreter,
    create_linkedin_modal_interpretation_formatter,
    create_notifier,
)
from job_hunter_agent.linkedin_application import LinkedInApplicationPageState
from job_hunter_agent.domain import JobPosting
from job_hunter_agent.notifier import NullNotifier


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

    async def test_handle_application_submit_returns_service_message(self) -> None:
        class _SubmissionService:
            def __init__(self) -> None:
                self.called_with: list[int] = []

            def run_for_application(self, application_id: int):
                self.called_with.append(application_id)
                return type(
                    "Result",
                    (),
                    {
                        "outcome": "submitted",
                        "detail": "submissao real concluida",
                        "application_status": "submitted",
                    },
                )

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.application_submission = _SubmissionService()

        reply = await app.handle_application_submit(42)

        self.assertEqual(app.application_submission.called_with, [42])
        self.assertEqual(reply, "Submissao: submissao real concluida (status=submitted)")

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


class CompositionTests(IsolatedAsyncioTestCase):
    async def test_build_known_job_lookup_checks_jobs_and_seen_jobs(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.job_urls: list[str] = []
                self.seen_urls: list[str] = []

            def job_url_exists(self, url: str) -> bool:
                self.job_urls.append(url)
                return False

            def seen_job_url_exists(self, url: str) -> bool:
                self.seen_urls.append(url)
                return url.endswith("known")

        repository = _Repository()
        lookup = build_known_job_lookup(repository)

        self.assertTrue(lookup("https://example.com/known"))
        self.assertEqual(repository.job_urls, ["https://example.com/known"])
        self.assertEqual(repository.seen_urls, ["https://example.com/known"])

    async def test_create_notifier_returns_null_notifier_when_telegram_disabled(self) -> None:
        notifier = create_notifier(
            settings=object(),
            repository=object(),
            enable_telegram=False,
            on_approved=None,
            on_application_preflight=None,
            on_application_submit=None,
        )

        self.assertIsInstance(notifier, NullNotifier)

    async def test_create_linkedin_modal_interpretation_formatter_returns_none_when_disabled(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "linkedin_modal_llm_enabled": False,
            },
        )()

        formatter = create_linkedin_modal_interpretation_formatter(settings)

        self.assertIsNone(formatter)

    async def test_create_linkedin_modal_interpreter_returns_none_when_disabled(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "linkedin_modal_llm_enabled": False,
            },
        )()

        interpreter = create_linkedin_modal_interpreter(settings)

        self.assertIsNone(interpreter)

    async def test_create_linkedin_modal_interpretation_formatter_formats_guarded_output(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "linkedin_modal_llm_enabled": True,
                "ollama_model": "dummy",
                "ollama_url": "http://localhost:11434",
            },
        )()

        class _Interpreter:
            def interpret(self, state):
                from job_hunter_agent.linkedin_modal_llm import LinkedInModalInterpretation

                return LinkedInModalInterpretation(
                    step_type="review_final",
                    recommended_action="submit_if_authorized",
                    confidence=0.91,
                    rationale="botao final visivel",
                )

        from unittest.mock import patch

        with patch("job_hunter_agent.composition.OllamaLinkedInModalInterpreter", return_value=_Interpreter()):
            formatter = create_linkedin_modal_interpretation_formatter(settings)

        rendered = formatter(
            LinkedInApplicationPageState(
                modal_open=True,
                modal_submit_visible=True,
                ready_to_submit=True,
            )
        )

        self.assertIn("interpretacao_modal=", rendered)
        self.assertIn("acao=submit_if_authorized", rendered)

    async def test_create_linkedin_modal_interpreter_returns_guarded_output(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "linkedin_modal_llm_enabled": True,
                "ollama_model": "dummy",
                "ollama_url": "http://localhost:11434",
            },
        )()

        class _Interpreter:
            def interpret(self, state):
                from job_hunter_agent.linkedin_modal_llm import LinkedInModalInterpretation

                return LinkedInModalInterpretation(
                    step_type="review_final",
                    recommended_action="submit_if_authorized",
                    confidence=0.91,
                    rationale="botao final visivel",
                )

        with patch("job_hunter_agent.composition.OllamaLinkedInModalInterpreter", return_value=_Interpreter()):
            interpreter = create_linkedin_modal_interpreter(settings)

        interpreted = interpreter(
            LinkedInApplicationPageState(
                modal_open=True,
                modal_submit_visible=True,
                ready_to_submit=True,
            )
        )

        self.assertEqual(interpreted.recommended_action, "submit_if_authorized")
        self.assertGreater(interpreted.confidence, 0.8)
