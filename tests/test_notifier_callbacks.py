import shutil
from unittest import TestCase

from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.infrastructure.notifier_callbacks import NotifierCallbackService
from job_hunter_agent.infrastructure.repository import SqliteJobRepository
from tests.tmp_workspace import prepare_workspace_tmp_dir


def sample_job(status: str = "collected") -> JobPosting:
    return JobPosting(
        title="Senior Kotlin Engineer",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url="https://example.com/job-1",
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia ao perfil.",
        external_key="key-1",
        id=1,
        status=status,
    )


class NotifierCallbackServiceTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = prepare_workspace_tmp_dir("notifier-callbacks")
        self.repository = SqliteJobRepository(self.temp_dir / "jobs.db")
        self.service = NotifierCallbackService(self.repository)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_handle_approve_marks_job_and_requests_followup(self) -> None:
        job = self.repository.save_new_jobs([sample_job()])[0]

        outcome = self.service.handle(f"approve:{job.id}")

        self.assertEqual(outcome.approved_job_ids, (job.id,))
        self.assertIn("aprovada", outcome.reply_text)
        self.assertEqual(self.repository.get_job(job.id).status, "approved")

    def test_handle_application_preflight_returns_requested_callback(self) -> None:
        job = self.repository.save_new_jobs([sample_job(status="approved")])[0]
        self.repository.mark_status(job.id, "approved")
        application = self.repository.create_application_draft(job.id, support_level="manual_review")
        self.repository.mark_application_status(application.id, status="confirmed")

        outcome = self.service.handle(f"app_preflight:{application.id}")

        self.assertEqual(outcome.requested_preflight_application_id, application.id)
        self.assertIn("Executando preflight", outcome.reply_text)

    def test_handle_application_transition_persists_status_change(self) -> None:
        job = self.repository.save_new_jobs([sample_job(status="approved")])[0]
        self.repository.mark_status(job.id, "approved")
        application = self.repository.create_application_draft(job.id, support_level="manual_review")

        outcome = self.service.handle(f"app_prepare:{application.id}")

        self.assertIn("pronta para revisao", outcome.reply_text)
        self.assertEqual(self.repository.get_application(application.id).status, "ready_for_review")
