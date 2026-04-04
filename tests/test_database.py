import shutil
import unittest

from job_hunter_agent.applicant import (
    ApplicationPreparationService,
    ApplicationPreflightService,
    ApplicationSupportAssessment,
    classify_job_application_support,
    parse_application_support_response,
)
from job_hunter_agent.domain import JobPosting
from job_hunter_agent.job_identity import PortalAwareJobIdentityStrategy
from job_hunter_agent.repository import SqliteJobRepository
from tests.tmp_workspace import prepare_workspace_tmp_dir


def sample_job(url: str, external_key: str) -> JobPosting:
    return JobPosting(
        title="Senior Kotlin Engineer",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url=url,
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia ao perfil.",
        external_key=external_key,
    )


class SqliteJobRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = prepare_workspace_tmp_dir("db")
        self.db_path = self.temp_dir / "jobs.db"
        self.repository = SqliteJobRepository(self.db_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_new_jobs_ignores_duplicates(self) -> None:
        first = sample_job("https://example.com/job-1", "key-1")
        duplicate = sample_job("https://example.com/job-1", "key-1")

        saved_first = self.repository.save_new_jobs([first])
        saved_second = self.repository.save_new_jobs([duplicate])

        self.assertEqual(len(saved_first), 1)
        self.assertEqual(len(saved_second), 0)

    def test_save_new_jobs_ignores_duplicate_external_key(self) -> None:
        first = sample_job("https://example.com/job-1", "key-1")
        duplicate_external_key = sample_job("https://example.com/job-2", "key-1")

        saved_first = self.repository.save_new_jobs([first])
        saved_second = self.repository.save_new_jobs([duplicate_external_key])

        self.assertEqual(len(saved_first), 1)
        self.assertEqual(len(saved_second), 0)

    def test_job_url_exists_checks_existing_url(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])

        self.assertEqual(len(saved), 1)
        self.assertTrue(self.repository.job_url_exists("https://example.com/job-1"))
        self.assertFalse(self.repository.job_url_exists("https://example.com/job-2"))

    def test_job_url_exists_matches_linkedin_variants_by_job_id(self) -> None:
        saved = self.repository.save_new_jobs(
            [sample_job("https://www.linkedin.com/jobs/view/123456789/?trackingId=abc", "key-1")]
        )

        self.assertEqual(len(saved), 1)
        self.assertTrue(self.repository.job_url_exists("https://www.linkedin.com/jobs/view/123456789/"))
        self.assertTrue(
            self.repository.job_exists(
                "https://www.linkedin.com/jobs/view/123456789/?currentJobId=123456789",
                "different-key",
            )
        )

    def test_remember_seen_job_persists_and_updates_seen_registry(self) -> None:
        self.repository.remember_seen_job(
            "https://example.com/job-1",
            "key-1",
            "LinkedIn",
            "discarded_rule:modalidade fora do perfil",
        )
        self.repository.remember_seen_job(
            "https://example.com/job-1",
            "key-1",
            "LinkedIn",
            "discarded_score:2",
        )

        self.assertTrue(self.repository.seen_job_exists("https://example.com/job-1", "key-1"))
        self.assertTrue(self.repository.seen_job_url_exists("https://example.com/job-1"))
        self.assertFalse(self.repository.seen_job_exists("https://example.com/job-2", "key-2"))

    def test_seen_job_exists_matches_linkedin_variants_by_job_id(self) -> None:
        self.repository.remember_seen_job(
            "https://www.linkedin.com/jobs/view/987654321/?trackingId=abc",
            "key-1",
            "LinkedIn",
            "discarded_rule:modalidade fora do perfil",
        )

        self.assertTrue(self.repository.seen_job_url_exists("https://www.linkedin.com/jobs/view/987654321/"))
        self.assertTrue(
            self.repository.seen_job_exists(
                "https://www.linkedin.com/jobs/view/987654321/?currentJobId=987654321",
                "different-key",
            )
        )

    def test_identity_strategy_preserves_linkedin_lookup_patterns(self) -> None:
        strategy = PortalAwareJobIdentityStrategy()

        self.assertEqual(
            strategy.url_lookup_patterns("https://www.linkedin.com/jobs/view/123456789/?trackingId=abc"),
            [
                "https://www.linkedin.com/jobs/view/123456789/?trackingId=abc",
                "%/jobs/view/123456789%",
            ],
        )
        self.assertEqual(
            strategy.url_lookup_patterns("https://example.com/job-1"),
            ["https://example.com/job-1"],
        )

    def test_summary_counts_statuses(self) -> None:
        saved = self.repository.save_new_jobs(
            [
                sample_job("https://example.com/job-1", "key-1"),
                sample_job("https://example.com/job-2", "key-2"),
            ]
        )
        self.repository.mark_status(saved[0].id, "approved")
        self.repository.mark_status(saved[1].id, "rejected")

        summary = self.repository.summary()

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["approved"], 1)
        self.assertEqual(summary["rejected"], 1)

    def test_collection_run_is_started_and_finished(self) -> None:
        run = self.repository.start_collection_run()

        self.repository.finish_collection_run(
            run.id,
            status="success",
            jobs_seen=3,
            jobs_saved=2,
            errors=0,
        )

        with self.repository._connect() as connection:
            row = connection.execute(
                """
                SELECT status, jobs_seen, jobs_saved, errors, finished_at
                FROM collection_runs
                WHERE id = ?
                """,
                (run.id,),
            ).fetchone()

        self.assertEqual(row[0], "success")
        self.assertEqual(row[1], 3)
        self.assertEqual(row[2], 2)
        self.assertEqual(row[3], 0)
        self.assertIsNotNone(row[4])

    def test_interrupt_running_collection_runs_marks_stale_runs(self) -> None:
        first = self.repository.start_collection_run()
        second = self.repository.start_collection_run()
        self.repository.finish_collection_run(
            first.id,
            status="success",
            jobs_seen=1,
            jobs_saved=1,
            errors=0,
        )

        interrupted = self.repository.interrupt_running_collection_runs()

        self.assertEqual(interrupted, 1)
        with self.repository._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, status, finished_at
                FROM collection_runs
                ORDER BY id
                """
            ).fetchall()

        self.assertEqual(rows[0][1], "success")
        self.assertEqual(rows[1][1], "interrupted")
        self.assertIsNotNone(rows[1][2])

    def test_mark_status_rejects_invalid_transition_value(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])

        with self.assertRaises(ValueError):
            self.repository.mark_status(saved[0].id, "archived")

    def test_list_recent_jobs_returns_latest_first(self) -> None:
        self.repository.save_new_jobs(
            [
                sample_job("https://example.com/job-1", "key-1"),
                sample_job("https://example.com/job-2", "key-2"),
            ]
        )

        jobs = self.repository.list_recent_jobs(limit=2)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].url, "https://example.com/job-2")

    def test_create_application_draft_is_idempotent_per_job(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]

        first = self.repository.create_application_draft(saved.id, notes="aguardando definicao")
        second = self.repository.create_application_draft(saved.id)

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.job_id, saved.id)
        self.assertEqual(first.status, "draft")

    def test_create_application_draft_requires_existing_job(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.create_application_draft(999)

    def test_mark_application_status_and_summary(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]
        application = self.repository.create_application_draft(saved.id, notes="primeiro passo")

        self.repository.mark_application_status(application.id, status="ready_for_review")
        self.repository.mark_application_status(
            application.id,
            status="confirmed",
            notes="confirmado manualmente",
        )
        self.repository.mark_application_status(
            application.id,
            status="submitted",
            submitted_at="2026-04-04T10:00:00",
        )

        stored = self.repository.get_application_by_job(saved.id)
        summary = self.repository.application_summary()

        self.assertEqual(stored.status, "submitted")
        self.assertEqual(stored.notes, "confirmado manualmente")
        self.assertEqual(stored.submitted_at, "2026-04-04T10:00:00")
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["submitted"], 1)

    def test_mark_application_status_rejects_invalid_value(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]
        application = self.repository.create_application_draft(saved.id)

        with self.assertRaises(ValueError):
            self.repository.mark_application_status(application.id, status="queued")

    def test_list_applications_by_status(self) -> None:
        first_job = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]
        second_job = self.repository.save_new_jobs([sample_job("https://example.com/job-2", "key-2")])[0]
        first_application = self.repository.create_application_draft(first_job.id)
        second_application = self.repository.create_application_draft(second_job.id)

        self.repository.mark_application_status(first_application.id, status="ready_for_review")
        self.repository.mark_application_status(second_application.id, status="cancelled")

        ready = self.repository.list_applications_by_status("ready_for_review")
        cancelled = self.repository.list_applications_by_status("cancelled")

        self.assertEqual([item.job_id for item in ready], [first_job.id])
        self.assertEqual([item.job_id for item in cancelled], [second_job.id])

    def test_application_preparation_service_creates_drafts_only_for_approved_jobs(self) -> None:
        approved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]
        collected = self.repository.save_new_jobs([sample_job("https://example.com/job-2", "key-2")])[0]
        self.repository.mark_status(approved.id, "approved")

        service = ApplicationPreparationService(self.repository)

        drafts = service.create_drafts_for_approved_jobs(
            [approved.id, collected.id, 999],
            notes="rascunho criado apos aprovacao humana",
        )

        self.assertEqual([draft.job_id for draft in drafts], [approved.id])
        stored = self.repository.get_application_by_job(approved.id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.notes, "rascunho criado apos aprovacao humana")
        self.assertEqual(stored.support_level, "manual_review")
        self.assertIsNone(self.repository.get_application_by_job(collected.id))

    def test_application_preparation_service_uses_assessor_when_available(self) -> None:
        approved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]
        self.repository.mark_status(approved.id, "approved")

        class FakeAssessor:
            def assess(self, job: JobPosting) -> ApplicationSupportAssessment:
                return ApplicationSupportAssessment(
                    support_level="auto_supported",
                    rationale="fluxo simples detectado",
                )

        service = ApplicationPreparationService(self.repository, support_assessor=FakeAssessor())

        drafts = service.create_drafts_for_approved_jobs([approved.id])

        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].support_level, "auto_supported")
        self.assertEqual(drafts[0].support_rationale, "fluxo simples detectado")

    def test_application_preparation_service_falls_back_when_assessor_fails(self) -> None:
        approved = self.repository.save_new_jobs([sample_job("https://www.linkedin.com/jobs/view/123", "key-1")])[0]
        self.repository.mark_status(approved.id, "approved")

        class BrokenAssessor:
            def assess(self, job: JobPosting) -> ApplicationSupportAssessment:
                raise RuntimeError("falha")

        service = ApplicationPreparationService(self.repository, support_assessor=BrokenAssessor())

        drafts = service.create_drafts_for_approved_jobs([approved.id])

        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].support_level, "manual_review")

    def test_parse_application_support_response_accepts_valid_json(self) -> None:
        assessment = parse_application_support_response(
            '{"support_level":"manual_review","rationale":"requer confirmacao humana"}'
        )

        self.assertEqual(assessment.support_level, "manual_review")
        self.assertEqual(assessment.rationale, "requer confirmacao humana")

    def test_parse_application_support_response_rejects_invalid_support_level(self) -> None:
        assessment = parse_application_support_response('{"support_level":"maybe"}')

        self.assertEqual(assessment.support_level, "unsupported")
        self.assertIn("invalido", assessment.rationale)

    def test_create_application_draft_persists_support_metadata(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]

        draft = self.repository.create_application_draft(
            saved.id,
            support_level="unsupported",
            support_rationale="portal externo nao suportado",
        )

        self.assertEqual(draft.support_level, "unsupported")
        self.assertEqual(draft.support_rationale, "portal externo nao suportado")

    def test_classify_job_application_support_is_conservative(self) -> None:
        linkedin_job = sample_job("https://www.linkedin.com/jobs/view/123", "key-1")
        gupy_job = sample_job("https://empresa.gupy.io/job/123", "key-2")
        indeed_job = sample_job("https://www.indeed.com/viewjob?jk=123", "key-3")

        self.assertEqual(classify_job_application_support(linkedin_job).support_level, "manual_review")
        self.assertEqual(classify_job_application_support(gupy_job).support_level, "unsupported")
        self.assertEqual(classify_job_application_support(indeed_job).support_level, "manual_review")

    def test_application_preflight_keeps_confirmed_linkedin_as_confirmed(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://www.linkedin.com/jobs/view/123", "key-1")])[0]
        application = self.repository.create_application_draft(
            saved.id,
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(application.id, status="confirmed")

        result = ApplicationPreflightService(self.repository).run_for_application(application.id)

        stored = self.repository.get_application(application.id)
        self.assertEqual(result.outcome, "ready")
        self.assertEqual(result.application_status, "confirmed")
        self.assertEqual(stored.status, "confirmed")
        self.assertIn("preflight ok", stored.notes)
        self.assertEqual(stored.last_error, "")

    def test_application_preflight_moves_unsupported_to_error_submit(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://empresa.gupy.io/job/123", "key-1")])[0]
        application = self.repository.create_application_draft(
            saved.id,
            support_level="unsupported",
            support_rationale="portal externo com formulario proprio ainda nao suportado",
        )
        self.repository.mark_application_status(application.id, status="confirmed")

        result = ApplicationPreflightService(self.repository).run_for_application(application.id)

        stored = self.repository.get_application(application.id)
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.application_status, "error_submit")
        self.assertEqual(stored.status, "error_submit")
        self.assertIn("nao suportado", stored.last_error)
