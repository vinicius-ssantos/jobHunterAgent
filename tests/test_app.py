from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch
from unittest import IsolatedAsyncioTestCase

from job_hunter_agent.application.app import JobHunterApplication, parse_args, suggest_candidate_profile
from job_hunter_agent.application.composition import (
    build_known_job_lookup,
    create_application_preflight_service,
    create_application_submission_service,
    create_linkedin_application_flow_inspector,
    create_linkedin_modal_interpreter,
    create_linkedin_modal_interpretation_formatter,
    create_notifier,
)
from job_hunter_agent.core.domain import JobApplication, JobApplicationEvent
from job_hunter_agent.collectors.linkedin_application import LinkedInApplicationPageState
from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.infrastructure.notifier import NullNotifier


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

    async def test_suggest_candidate_profile_returns_missing_resume_message(self) -> None:
        rendered = suggest_candidate_profile(
            resume_path=Path("resume-inexistente.pdf"),
            output_path=Path("candidate_profile.json"),
            model_name="qwen2.5:7b",
            base_url="http://localhost:11434",
        )

        self.assertIn("Curriculo nao encontrado", rendered)

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

        from job_hunter_agent.application.applicant import ApplicationPreparationService

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

    async def test_parse_args_accepts_applications_list_command(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "list", "--status", "confirmed"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "list")
        self.assertEqual(args.status, "confirmed")

    async def test_parse_args_accepts_jobs_list_command(self) -> None:
        with patch("sys.argv", ["main.py", "jobs", "list", "--status", "pending"]):
            args = parse_args()

        self.assertEqual(args.command, "jobs")
        self.assertEqual(args.jobs_command, "list")
        self.assertEqual(args.status, "pending")

    async def test_parse_args_accepts_status_command(self) -> None:
        with patch("sys.argv", ["main.py", "status"]):
            args = parse_args()

        self.assertEqual(args.command, "status")

    async def test_parse_args_accepts_jobs_approve_command(self) -> None:
        with patch("sys.argv", ["main.py", "jobs", "approve", "--id", "11"]):
            args = parse_args()

        self.assertEqual(args.command, "jobs")
        self.assertEqual(args.jobs_command, "approve")
        self.assertEqual(args.id, 11)

    async def test_parse_args_accepts_jobs_show_command(self) -> None:
        with patch("sys.argv", ["main.py", "jobs", "show", "--id", "11"]):
            args = parse_args()

        self.assertEqual(args.command, "jobs")
        self.assertEqual(args.jobs_command, "show")
        self.assertEqual(args.id, 11)

    async def test_parse_args_accepts_applications_prepare_command(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "prepare", "--id", "12"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "prepare")
        self.assertEqual(args.id, 12)

    async def test_parse_args_accepts_applications_create_command(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "create", "--job-id", "12"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "create")
        self.assertEqual(args.job_id, 12)

    async def test_parse_args_accepts_applications_artifacts_command(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "artifacts", "--limit", "2"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "artifacts")
        self.assertEqual(args.limit, 2)

    async def test_parse_args_accepts_applications_events_command(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "events", "--id", "7", "--limit", "3"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "events")
        self.assertEqual(args.id, 7)
        self.assertEqual(args.limit, 3)

    async def test_parse_args_accepts_applications_submit_command(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "submit", "--id", "7"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "submit")
        self.assertEqual(args.id, 7)

    async def test_parse_args_accepts_candidate_profile_suggest_command(self) -> None:
        with patch("sys.argv", ["main.py", "candidate-profile", "suggest"]):
            args = parse_args()

        self.assertEqual(args.command, "candidate-profile")
        self.assertEqual(args.candidate_profile_command, "suggest")

    async def test_parse_args_rejects_operational_command_with_agora(self) -> None:
        with patch("sys.argv", ["main.py", "--agora", "applications", "list"]):
            with self.assertRaises(SystemExit):
                parse_args()


class ApplicationCliTests(IsolatedAsyncioTestCase):
    async def test_show_status_overview_renders_job_and_application_counts(self) -> None:
        class _Repository:
            def summary(self):
                return {
                    "total": 3,
                    "collected": 1,
                    "approved": 1,
                    "rejected": 1,
                    "error_collect": 0,
                }

            def application_summary(self):
                return {
                    "total": 2,
                    "draft": 1,
                    "ready_for_review": 0,
                    "confirmed": 1,
                    "authorized_submit": 0,
                    "submitted": 0,
                    "error_submit": 0,
                    "cancelled": 0,
                }

            def list_applications_by_status(self, status: str):
                if status == "authorized_submit":
                    return [
                        JobApplication(
                            id=1,
                            job_id=10,
                            status="authorized_submit",
                            support_level="manual_review",
                            last_preflight_detail="preflight real | pronto_para_envio=sim | ok: fluxo pronto para submissao assistida no LinkedIn",
                        )
                    ]
                if status == "error_submit":
                    return [
                        JobApplication(
                            id=2,
                            job_id=11,
                            status="error_submit",
                            support_level="manual_review",
                            last_error="readiness=listing_redirect | motivo=a navegacao caiu em listagem ou colecao do LinkedIn | pagina=https://www.linkedin.com/jobs/collections/similar-jobs/",
                        )
                    ]
                return []

            def list_recent_application_events_since(self, since: str):
                return [
                    JobApplicationEvent(
                        id=1,
                        application_id=1,
                        event_type="preflight_ready",
                        detail="preflight real | pronto_para_envio=sim | ok: fluxo pronto para submissao assistida no LinkedIn",
                        created_at="2026-04-08T10:00:00",
                    ),
                    JobApplicationEvent(
                        id=2,
                        application_id=2,
                        event_type="submit_error",
                        detail="readiness=listing_redirect | motivo=a navegacao caiu em listagem ou colecao do LinkedIn | pagina=https://www.linkedin.com/jobs/collections/similar-jobs/",
                        created_at="2026-04-08T10:01:00",
                    ),
                ]

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        rendered = app.show_status_overview()

        self.assertIn("Resumo operacional:", rendered)
        self.assertIn("- approved=1", rendered)
        self.assertIn("- draft=1", rendered)
        self.assertIn("- confirmed=1", rendered)
        self.assertIn("operacao:", rendered)
        self.assertIn("- pronto_para_envio=1", rendered)
        self.assertIn("- similar_jobs=1", rendered)

    async def test_build_execution_summary_renders_preflights_submits_and_block_counts(self) -> None:
        class _Repository:
            def list_recent_application_events_since(self, since: str):
                return [
                    JobApplicationEvent(
                        id=1,
                        application_id=1,
                        event_type="preflight_ready",
                        detail="preflight real | pronto_para_envio=sim | ok: fluxo pronto para submissao assistida no LinkedIn",
                        created_at="2026-04-08T10:00:00",
                    ),
                    JobApplicationEvent(
                        id=2,
                        application_id=2,
                        event_type="preflight_blocked",
                        detail="readiness=no_apply_cta | motivo=a vaga so oferece candidatura externa no site da empresa",
                        created_at="2026-04-08T10:01:00",
                    ),
                    JobApplicationEvent(
                        id=3,
                        application_id=3,
                        event_type="submit_error",
                        detail="readiness=listing_redirect | motivo=a navegacao caiu em listagem ou colecao do LinkedIn | pagina=https://www.linkedin.com/jobs/collections/similar-jobs/",
                        created_at="2026-04-08T10:02:00",
                    ),
                    JobApplicationEvent(
                        id=4,
                        application_id=4,
                        event_type="submit_submitted",
                        detail="submissao real concluida no LinkedIn",
                        created_at="2026-04-08T10:03:00",
                    ),
                ]

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        rendered = app.build_execution_summary("2026-04-08T09:59:00")

        self.assertIn("Execucao operacional:", rendered)
        self.assertIn("- preflights_concluidos=2", rendered)
        self.assertIn("- submits_concluidos=2", rendered)
        self.assertIn("candidatura_externa=1", rendered)
        self.assertIn("similar_jobs=1", rendered)

    async def test_create_application_draft_for_job_creates_draft_for_approved_job(self) -> None:
        class _Repository:
            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="approved")

            def get_application_by_job(self, job_id: int):
                return None

        class _PreparationService:
            def __init__(self) -> None:
                self.calls: list[tuple[list[int], str]] = []

            def create_drafts_for_approved_jobs(self, job_ids: list[int], notes: str = ""):
                self.calls.append((job_ids, notes))
                return [
                    JobApplication(
                        id=15,
                        job_id=job_ids[0],
                        status="draft",
                        support_level="manual_review",
                    )
                ]

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()
        app.application_preparation = _PreparationService()

        rendered = app.create_application_draft_for_job(10)

        self.assertIn("Rascunho criado: application_id=15 job_id=10 status=draft", rendered)
        self.assertEqual(
            app.application_preparation.calls,
            [([10], "rascunho criado via cli apos aprovacao humana")],
        )

    async def test_create_application_draft_for_job_reports_existing_application(self) -> None:
        class _Repository:
            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="approved")

            def get_application_by_job(self, job_id: int):
                return JobApplication(
                    id=21,
                    job_id=job_id,
                    status="confirmed",
                    support_level="manual_review",
                )

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()
        app.application_preparation = object()

        rendered = app.create_application_draft_for_job(10)

        self.assertEqual(
            rendered,
            "Candidatura ja existe para a vaga: application_id=21 status=confirmed job_id=10",
        )

    async def test_create_application_draft_for_job_rejects_non_approved_job(self) -> None:
        class _Repository:
            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="collected")

            def get_application_by_job(self, job_id: int):
                return None

        class _PreparationService:
            def create_drafts_for_approved_jobs(self, job_ids: list[int], notes: str = ""):
                return []

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()
        app.application_preparation = _PreparationService()

        rendered = app.create_application_draft_for_job(10)

        self.assertEqual(rendered, "Vaga ainda nao foi aprovada para criar candidatura: id=10")

    async def test_show_job_renders_job_detail_with_linked_application(self) -> None:
        class _Repository:
            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="approved")

            def get_application_by_job(self, job_id: int):
                return JobApplication(
                    id=4,
                    job_id=job_id,
                    status="confirmed",
                    support_level="manual_review",
                )

            def list_job_events(self, job_id: int, limit: int = 5):
                return []

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        rendered = app.show_job(10)

        self.assertIn("titulo=Backend Java", rendered)
        self.assertIn("empresa=ACME", rendered)
        self.assertIn("application_id=4", rendered)
        self.assertIn("application_status=confirmed", rendered)

    async def test_show_job_renders_recent_job_events(self) -> None:
        class _Repository:
            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="approved")

            def get_application_by_job(self, job_id: int):
                return None

            def list_job_events(self, job_id: int, limit: int = 5):
                from job_hunter_agent.core.domain import JobStatusEvent

                return [
                    JobStatusEvent(
                        id=2,
                        job_id=job_id,
                        event_type="status_changed",
                        detail="Vaga aprovada: Backend Java - ACME",
                        from_status="collected",
                        to_status="approved",
                        created_at="2026-04-07T12:00:00",
                    )
                ]

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        rendered = app.show_job(10)

        self.assertIn("eventos_recentes:", rendered)
        self.assertIn("status_changed", rendered)
        self.assertIn("Vaga aprovada: Backend Java - ACME", rendered)

    async def test_list_applications_renders_existing_items(self) -> None:
        class _Repository:
            def list_applications_by_status(self, status: str):
                if status == "confirmed":
                    return [
                        JobApplication(
                            id=2,
                            job_id=10,
                            status="confirmed",
                            support_level="manual_review",
                            last_preflight_detail="preflight real inconclusivo | perguntas_pendentes=ha quantos anos voce usa java?",
                        )
                    ]
                return []

            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="approved")

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        rendered = app.list_applications(status="confirmed")

        self.assertIn("Candidaturas listadas: 1", rendered)
        self.assertIn("2: confirmed", rendered)
        self.assertIn("Backend Java | ACME", rendered)
        self.assertIn("op=perguntas_adicionais", rendered)

    async def test_list_applications_supports_ready_alias_from_cli_mapping(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.seen_statuses: list[str] = []

            def list_applications_by_status(self, status: str):
                self.seen_statuses.append(status)
                if status == "authorized_submit":
                    return [JobApplication(id=9, job_id=10, status="authorized_submit", support_level="manual_review")]
                return []

            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="approved")

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        rendered = app.list_applications(status="authorized_submit")

        self.assertIn("9: authorized_submit", rendered)
        self.assertEqual(app.repository.seen_statuses, ["authorized_submit"])

    async def test_show_application_renders_recent_events(self) -> None:
        class _Repository:
            def get_application(self, application_id: int):
                return JobApplication(
                    id=application_id,
                    job_id=10,
                    status="confirmed",
                    support_level="manual_review",
                    notes="contexto humano",
                    last_preflight_detail="preflight real ok",
                    last_submit_detail="submissao ainda nao executada",
                )

            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="approved")

            def list_application_events(self, application_id: int, limit: int = 5):
                return [
                    JobApplicationEvent(
                        id=3,
                        application_id=application_id,
                        event_type="preflight_ready",
                        detail="CTA encontrado",
                        from_status="confirmed",
                        to_status="confirmed",
                        created_at="2026-04-07T10:00:00",
                    )
                ]

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        rendered = app.show_application(2)

        self.assertIn("eventos_recentes:", rendered)
        self.assertIn("last_preflight_detail=preflight real ok", rendered)
        self.assertIn("last_submit_detail=submissao ainda nao executada", rendered)
        self.assertIn("preflight_ready", rendered)
        self.assertIn("CTA encontrado", rendered)

    async def test_show_application_events_renders_event_stream(self) -> None:
        class _Repository:
            def get_application(self, application_id: int):
                return JobApplication(id=application_id, job_id=10, status="confirmed")

            def list_application_events(self, application_id: int, limit: int = 10):
                return [
                    JobApplicationEvent(
                        id=4,
                        application_id=application_id,
                        event_type="submit_submitted",
                        detail="submissao real concluida no LinkedIn",
                        from_status="authorized_submit",
                        to_status="submitted",
                        created_at="2026-04-07T11:00:00",
                    )
                ]

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        rendered = app.show_application_events(2, limit=5)

        self.assertIn("Eventos da candidatura 2: 1", rendered)
        self.assertIn("submit_submitted", rendered)
        self.assertIn("authorized_submit -> submitted", rendered)
        self.assertIn("submissao real concluida no LinkedIn", rendered)

    async def test_transition_application_updates_valid_state(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.marked: list[tuple[int, str]] = []

            def get_application(self, application_id: int):
                return JobApplication(id=application_id, job_id=5, status="draft")

            def mark_application_status(
                self,
                application_id: int,
                *,
                status: str,
                event_detail="",
                notes=None,
                last_preflight_detail=None,
                last_submit_detail=None,
                last_error=None,
                submitted_at=None,
            ):
                self.marked.append((application_id, status, event_detail))

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        detail = app.transition_application(3, "app_prepare")

        self.assertEqual(detail, "Candidatura pronta para revisao: id=3")
        self.assertEqual(
            app.repository.marked,
            [(3, "ready_for_review", "Candidatura pronta para revisao: id=3")],
        )

    async def test_show_latest_failure_artifacts_renders_recent_files(self) -> None:
        temp_dir = Path(self.id().replace(".", "_"))
        temp_root = Path.cwd() / ".tmp-tests" / temp_dir
        temp_root.mkdir(parents=True, exist_ok=True)
        first = temp_root / "2026-04-07_10-00-00_preflight_job-1_meta.json"
        second = temp_root / "2026-04-07_11-00-00_submit_job-2_meta.json"
        first.write_text("{}", encoding="utf-8")
        second.write_text("{}", encoding="utf-8")
        try:
            app = JobHunterApplication.__new__(JobHunterApplication)
            app.settings = type("Settings", (), {"failure_artifacts_dir": temp_root})()

            rendered = app.show_latest_failure_artifacts(limit=2)

            self.assertIn("Artefatos recentes: 2", rendered)
            self.assertIn(second.name, rendered)
            self.assertIn(first.name, rendered)
        finally:
            for item in temp_root.glob("*"):
                item.unlink()
            temp_root.rmdir()


class JobCliTests(IsolatedAsyncioTestCase):
    async def test_list_jobs_renders_existing_items(self) -> None:
        class _Repository:
            def list_jobs_by_status(self, status: str):
                if status == "collected":
                    return [_sample_job(job_id=4, status="collected")]
                return []

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        rendered = app.list_jobs(status="collected")

        self.assertIn("Vagas listadas: 1", rendered)
        self.assertIn("4: collected | Backend Java | ACME", rendered)

    async def test_review_job_approves_valid_transition(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.marked: list[tuple[int, str]] = []

            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="collected")

            def mark_status(self, job_id: int, status: str, *, detail: str = ""):
                self.marked.append((job_id, status, detail))

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        detail = app.review_job(8, "approve")

        self.assertEqual(detail, "Vaga aprovada: Backend Java - ACME")
        self.assertEqual(
            app.repository.marked,
            [(8, "approved", "Vaga aprovada: Backend Java - ACME")],
        )

    async def test_review_job_rejects_invalid_transition(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.marked: list[tuple[int, str]] = []

            def get_job(self, job_id: int):
                return _sample_job(job_id=job_id, status="approved")

            def mark_status(self, job_id: int, status: str, *, detail: str = ""):
                self.marked.append((job_id, status, detail))

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        detail = app.review_job(8, "approve")

        self.assertEqual(detail, "Vaga ja estava aprovada: Backend Java - ACME")
        self.assertEqual(app.repository.marked, [])

    async def test_authorize_application_updates_status_when_transition_is_valid(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.marked: list[tuple[int, str]] = []

            def get_application(self, application_id: int):
                return JobApplication(id=application_id, job_id=5, status="confirmed")

            def mark_application_status(
                self,
                application_id: int,
                *,
                status: str,
                event_detail="",
                notes=None,
                last_preflight_detail=None,
                last_submit_detail=None,
                last_error=None,
                submitted_at=None,
            ):
                self.marked.append((application_id, status, event_detail))

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        detail = app.authorize_application(9)

        self.assertEqual(detail, "Candidatura autorizada para envio: id=9")
        self.assertEqual(
            app.repository.marked,
            [(9, "authorized_submit", "Candidatura autorizada para envio: id=9")],
        )

    async def test_authorize_application_reports_invalid_transition(self) -> None:
        class _Repository:
            def get_application(self, application_id: int):
                return JobApplication(id=application_id, job_id=5, status="draft")

        app = JobHunterApplication.__new__(JobHunterApplication)
        app.repository = _Repository()

        detail = app.authorize_application(4)

        self.assertEqual(detail, "Candidatura ainda nao foi preparada para envio: id=4")


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
                from job_hunter_agent.collectors.linkedin_modal_llm import LinkedInModalInterpretation

                return LinkedInModalInterpretation(
                    step_type="review_final",
                    recommended_action="submit_if_authorized",
                    confidence=0.91,
                    rationale="botao final visivel",
                )

        from unittest.mock import patch

        with patch("job_hunter_agent.application.composition.OllamaLinkedInModalInterpreter", return_value=_Interpreter()):
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
                from job_hunter_agent.collectors.linkedin_modal_llm import LinkedInModalInterpretation

                return LinkedInModalInterpretation(
                    step_type="review_final",
                    recommended_action="submit_if_authorized",
                    confidence=0.91,
                    rationale="botao final visivel",
                )

        with patch("job_hunter_agent.application.composition.OllamaLinkedInModalInterpreter", return_value=_Interpreter()):
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

    async def test_create_linkedin_application_flow_inspector_preflight_uses_formatter_only(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "linkedin_storage_state_path": "linkedin-state.json",
                "browser_headless": True,
                "resume_path": "resume.pdf",
                "application_contact_email": "vinicius@example.com",
                "application_phone": "11999999999",
                "application_phone_country_code": "55",
                "candidate_profile_path": "candidate_profile.json",
                "save_failure_artifacts": True,
                "failure_artifacts_dir": ".tmp-tests/failure-artifacts",
            },
        )()

        candidate_profile = object()
        formatter = object()
        components = object()

        with patch(
            "job_hunter_agent.application.composition.load_candidate_profile",
            return_value=candidate_profile,
        ) as load_profile, patch(
            "job_hunter_agent.application.composition.create_linkedin_application_flow_components",
            return_value=components,
        ) as create_components, patch(
            "job_hunter_agent.application.composition.create_linkedin_modal_interpretation_formatter",
            return_value=formatter,
        ) as create_formatter, patch(
            "job_hunter_agent.application.composition.create_linkedin_modal_interpreter"
        ) as create_interpreter, patch(
            "job_hunter_agent.application.composition.LinkedInApplicationFlowInspector",
            return_value="inspector-preflight",
        ) as inspector_factory:
            inspector = create_linkedin_application_flow_inspector(settings, mode="preflight")

        self.assertEqual(inspector, "inspector-preflight")
        load_profile.assert_called_once_with("candidate_profile.json")
        create_components.assert_called_once()
        create_formatter.assert_called_once_with(settings)
        create_interpreter.assert_not_called()
        kwargs = inspector_factory.call_args.kwargs  # type: ignore[attr-defined]
        self.assertEqual(kwargs["storage_state_path"], "linkedin-state.json")
        self.assertTrue(kwargs["headless"])
        self.assertEqual(kwargs["resume_path"], "resume.pdf")
        self.assertEqual(kwargs["contact_email"], "vinicius@example.com")
        self.assertEqual(kwargs["phone"], "11999999999")
        self.assertEqual(kwargs["phone_country_code"], "55")
        self.assertIs(kwargs["candidate_profile"], candidate_profile)
        self.assertEqual(kwargs["candidate_profile_path"], "candidate_profile.json")
        self.assertTrue(kwargs["save_failure_artifacts"])
        self.assertEqual(kwargs["failure_artifacts_dir"], ".tmp-tests/failure-artifacts")
        self.assertEqual(kwargs["modal_interpretation_formatter"], formatter)
        self.assertTrue(kwargs["artifact_capture"].enabled)
        self.assertEqual(str(kwargs["artifact_capture"].artifacts_dir), ".tmp-tests/failure-artifacts")
        self.assertIs(kwargs["components"], components)

    async def test_create_linkedin_application_flow_inspector_submit_uses_interpreter_only(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "linkedin_storage_state_path": "linkedin-state.json",
                "browser_headless": False,
                "resume_path": "resume.pdf",
                "application_contact_email": "vinicius@example.com",
                "application_phone": "11999999999",
                "application_phone_country_code": "55",
                "candidate_profile_path": "candidate_profile.json",
                "save_failure_artifacts": False,
                "failure_artifacts_dir": ".tmp-tests/failure-artifacts",
            },
        )()

        candidate_profile = object()
        interpreter = object()
        components = object()

        with patch(
            "job_hunter_agent.application.composition.load_candidate_profile",
            return_value=candidate_profile,
        ) as load_profile, patch(
            "job_hunter_agent.application.composition.create_linkedin_application_flow_components",
            return_value=components,
        ) as create_components, patch(
            "job_hunter_agent.application.composition.create_linkedin_modal_interpretation_formatter"
        ) as create_formatter, patch(
            "job_hunter_agent.application.composition.create_linkedin_modal_interpreter",
            return_value=interpreter,
        ) as create_interpreter, patch(
            "job_hunter_agent.application.composition.LinkedInApplicationFlowInspector",
            return_value="inspector-submit",
        ) as inspector_factory:
            inspector = create_linkedin_application_flow_inspector(settings, mode="submit")

        self.assertEqual(inspector, "inspector-submit")
        load_profile.assert_called_once_with("candidate_profile.json")
        create_components.assert_called_once()
        create_formatter.assert_not_called()
        create_interpreter.assert_called_once_with(settings)
        kwargs = inspector_factory.call_args.kwargs  # type: ignore[attr-defined]
        self.assertEqual(kwargs["storage_state_path"], "linkedin-state.json")
        self.assertFalse(kwargs["headless"])
        self.assertEqual(kwargs["resume_path"], "resume.pdf")
        self.assertEqual(kwargs["contact_email"], "vinicius@example.com")
        self.assertEqual(kwargs["phone"], "11999999999")
        self.assertEqual(kwargs["phone_country_code"], "55")
        self.assertIs(kwargs["candidate_profile"], candidate_profile)
        self.assertEqual(kwargs["candidate_profile_path"], "candidate_profile.json")
        self.assertFalse(kwargs["save_failure_artifacts"])
        self.assertEqual(kwargs["failure_artifacts_dir"], ".tmp-tests/failure-artifacts")
        self.assertEqual(kwargs["modal_interpreter"], interpreter)
        self.assertFalse(kwargs["artifact_capture"].enabled)
        self.assertEqual(str(kwargs["artifact_capture"].artifacts_dir), ".tmp-tests/failure-artifacts")
        self.assertIs(kwargs["components"], components)

    async def test_create_linkedin_application_flow_inspector_rejects_unsupported_mode(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "linkedin_storage_state_path": "linkedin-state.json",
                "browser_headless": True,
                "resume_path": "resume.pdf",
                "application_contact_email": "vinicius@example.com",
                "application_phone": "11999999999",
                "application_phone_country_code": "55",
                "candidate_profile_path": "candidate_profile.json",
                "save_failure_artifacts": False,
                "failure_artifacts_dir": ".tmp-tests/failure-artifacts",
            },
        )()

        with patch(
            "job_hunter_agent.application.composition.load_candidate_profile",
            return_value=object(),
        ):
            with self.assertRaisesRegex(ValueError, "modo de inspector do LinkedIn nao suportado"):
                create_linkedin_application_flow_inspector(settings, mode="unknown")

    async def test_create_application_preflight_service_uses_preflight_mode(self) -> None:
        repository = object()
        settings = type(
            "Settings",
            (),
            {
                "linkedin_storage_state_path": "linkedin-state.json",
                "resume_path": "resume.pdf",
                "application_contact_email": "vinicius@example.com",
                "application_phone": "11999999999",
                "application_phone_country_code": "55",
            },
        )()
        readiness_checker = object()

        with patch(
            "job_hunter_agent.application.composition.create_linkedin_preflight_inspector",
            return_value="preflight-inspector",
        ) as create_inspector, patch(
            "job_hunter_agent.application.composition.ApplicationReadinessCheckService",
            return_value=readiness_checker,
        ) as readiness_factory:
            service = create_application_preflight_service(repository, settings)

        create_inspector.assert_called_once_with(settings)
        readiness_factory.assert_called_once_with(
            linkedin_storage_state_path="linkedin-state.json",
            resume_path="resume.pdf",
            contact_email="vinicius@example.com",
            phone="11999999999",
            phone_country_code="55",
        )
        self.assertIs(service.repository, repository)
        self.assertEqual(service.flow_inspector, "preflight-inspector")
        self.assertIs(service.readiness_checker, readiness_checker)

    async def test_create_application_submission_service_uses_submit_mode_and_readiness_checker(self) -> None:
        repository = object()
        settings = type(
            "Settings",
            (),
            {
                "linkedin_storage_state_path": "linkedin-state.json",
                "resume_path": "resume.pdf",
                "application_contact_email": "vinicius@example.com",
                "application_phone": "11999999999",
                "application_phone_country_code": "55",
            },
        )()

        readiness_checker = object()

        with patch(
            "job_hunter_agent.application.composition.create_linkedin_submission_applicant",
            return_value="submit-inspector",
        ) as create_inspector, patch(
            "job_hunter_agent.application.composition.ApplicationReadinessCheckService",
            return_value=readiness_checker,
        ) as readiness_factory:
            service = create_application_submission_service(repository, settings)

        create_inspector.assert_called_once_with(settings)
        readiness_factory.assert_called_once_with(
            linkedin_storage_state_path="linkedin-state.json",
            resume_path="resume.pdf",
            contact_email="vinicius@example.com",
            phone="11999999999",
            phone_country_code="55",
        )
        self.assertIs(service.repository, repository)
        self.assertEqual(service.applicant, "submit-inspector")
        self.assertIs(service.readiness_checker, readiness_checker)
