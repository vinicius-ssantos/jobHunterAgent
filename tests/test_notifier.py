import shutil
from unittest import TestCase

from job_hunter_agent.domain import JobPosting
from job_hunter_agent.notifier import (
    NullNotifier,
    build_application_action_rows,
    build_application_card_message,
    build_application_preview_line,
    build_application_queue_message,
    build_job_card_message,
    build_missing_application_reply,
    build_missing_job_reply,
    resolve_application_preflight_request,
    resolve_application_action,
    resolve_review_action,
)
from job_hunter_agent.repository import SqliteJobRepository
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


class ReviewActionTests(TestCase):
    def test_approve_collected_job(self) -> None:
        next_status, reply = resolve_review_action(sample_job(), "approve")
        self.assertEqual(next_status, "approved")
        self.assertIn("aprovada", reply)

    def test_reject_collected_job(self) -> None:
        next_status, reply = resolve_review_action(sample_job(), "reject")
        self.assertEqual(next_status, "rejected")
        self.assertIn("ignorada", reply)

    def test_prevent_duplicate_approval(self) -> None:
        next_status, reply = resolve_review_action(sample_job(status="approved"), "approve")
        self.assertIsNone(next_status)
        self.assertIn("ja estava aprovada", reply)

    def test_invalid_action_is_rejected(self) -> None:
        next_status, reply = resolve_review_action(sample_job(), "archive")
        self.assertIsNone(next_status)
        self.assertIn("invalida", reply)

    def test_build_job_card_message_contains_essential_fields(self) -> None:
        message = build_job_card_message(sample_job())

        self.assertIn("Senior Kotlin Engineer", message)
        self.assertIn("Empresa: ACME", message)
        self.assertIn("Modalidade: remoto", message)
        self.assertIn("Relevancia: 8/10", message)
        self.assertIn("Abrir vaga", message)

    def test_build_missing_job_reply_is_safe(self) -> None:
        reply = build_missing_job_reply(999)

        self.assertIn("nao encontrada", reply)
        self.assertIn("999", reply)

    def test_build_missing_application_reply_is_safe(self) -> None:
        reply = build_missing_application_reply(123)

        self.assertIn("Candidatura nao encontrada", reply)
        self.assertIn("123", reply)

    def test_build_application_preview_line_uses_job_data(self) -> None:
        temp_dir = prepare_workspace_tmp_dir("application-preview")
        repository = SqliteJobRepository(temp_dir / "jobs.db")
        try:
            saved = repository.save_new_jobs([sample_job(status="approved")])[0]
            draft = repository.create_application_draft(
                saved.id,
                support_level="manual_review",
                support_rationale="linkedin interno ainda requer confirmacao",
            )

            line = build_application_preview_line(repository, draft)

            self.assertIn("Senior Kotlin Engineer", line)
            self.assertIn("[draft | manual_review]", line)
            self.assertIn("manual_review", line)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_resolve_application_action_happy_path(self) -> None:
        from job_hunter_agent.domain import JobApplication

        draft = JobApplication(id=10, job_id=1, status="draft")
        ready = JobApplication(id=10, job_id=1, status="ready_for_review")

        self.assertEqual(resolve_application_action(draft, "app_prepare")[0], "ready_for_review")
        self.assertEqual(resolve_application_action(ready, "app_confirm")[0], "confirmed")
        self.assertEqual(resolve_application_action(ready, "app_cancel")[0], "cancelled")

    def test_resolve_application_action_is_idempotent(self) -> None:
        from job_hunter_agent.domain import JobApplication

        confirmed = JobApplication(id=10, job_id=1, status="confirmed")
        cancelled = JobApplication(id=11, job_id=1, status="cancelled")

        self.assertIsNone(resolve_application_action(confirmed, "app_confirm")[0])
        self.assertIsNone(resolve_application_action(cancelled, "app_cancel")[0])

    def test_build_application_action_rows_varies_by_status(self) -> None:
        from job_hunter_agent.domain import JobApplication

        def button(label: str, callback_data: str) -> tuple[str, str]:
            return (label, callback_data)

        draft_rows = build_application_action_rows(JobApplication(id=1, job_id=1, status="draft"), button)
        ready_rows = build_application_action_rows(JobApplication(id=1, job_id=1, status="ready_for_review"), button)
        confirmed_rows = build_application_action_rows(JobApplication(id=1, job_id=1, status="confirmed"), button)

        self.assertEqual(draft_rows[0][0], ("Preparar", "app_prepare:1"))
        self.assertEqual(ready_rows[0][0], ("Confirmar", "app_confirm:1"))
        self.assertEqual(confirmed_rows[0][0], ("Validar fluxo", "app_preflight:1"))

    def test_resolve_application_preflight_request_requires_confirmed_status(self) -> None:
        from job_hunter_agent.domain import JobApplication

        confirmed = JobApplication(id=1, job_id=1, status="confirmed")
        draft = JobApplication(id=2, job_id=2, status="draft")

        self.assertEqual(resolve_application_preflight_request(confirmed), (True, "Executando preflight da candidatura: id=1"))
        self.assertEqual(
            resolve_application_preflight_request(draft),
            (False, "Candidatura ainda nao foi confirmada para preflight: id=2"),
        )


class NullNotifierTests(TestCase):
    def test_null_notifier_can_be_instantiated(self) -> None:
        notifier = NullNotifier()

        self.assertIsNotNone(notifier)


class PersistenceAndReviewIntegrationTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = prepare_workspace_tmp_dir("review-integration")
        self.repository = SqliteJobRepository(self.temp_dir / "jobs.db")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_persistence_and_review_work_together(self) -> None:
        saved = self.repository.save_new_jobs([sample_job()])
        self.assertEqual(len(saved), 1)

        job = self.repository.get_job(saved[0].id)
        self.assertIsNotNone(job)
        next_status, _ = resolve_review_action(job, "approve")

        self.assertEqual(next_status, "approved")
        self.repository.mark_status(saved[0].id, next_status)

        updated = self.repository.get_job(saved[0].id)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "approved")
        self.assertEqual(self.repository.summary()["approved"], 1)

    def test_build_application_queue_message_summarizes_drafts(self) -> None:
        approved_job = self.repository.save_new_jobs([sample_job(status="approved")])[0]
        self.repository.mark_status(approved_job.id, "approved")
        application = self.repository.create_application_draft(
            approved_job.id,
            notes="rascunho criado apos aprovacao humana",
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(application.id, status="ready_for_review")

        message = build_application_queue_message(self.repository)

        self.assertIn("Candidaturas:", message)
        self.assertIn("Prontas para revisao: 1", message)
        self.assertIn("Senior Kotlin Engineer - ACME [ready_for_review | manual_review]", message)

    def test_build_application_card_message_contains_support_and_notes(self) -> None:
        approved_job = self.repository.save_new_jobs([sample_job(status="approved")])[0]
        self.repository.mark_status(approved_job.id, "approved")
        application = self.repository.create_application_draft(
            approved_job.id,
            notes="rascunho criado apos aprovacao humana",
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )

        message = build_application_card_message(self.repository, application)

        self.assertIn("Candidatura", message)
        self.assertIn("Vaga: Senior Kotlin Engineer", message)
        self.assertIn("Suporte: manual_review", message)
        self.assertIn("Observacoes: rascunho criado apos aprovacao humana", message)
