import shutil
import unittest

from job_hunter_agent.application.applicant import (
    ApplicationPreparationService,
    ApplicationPreflightService,
    ApplicationSubmissionService,
    ApplicationSupportAssessment,
    classify_job_application_support,
    parse_application_support_response,
)
from job_hunter_agent.application.application_readiness import ApplicationReadinessCheckService
from job_hunter_agent.llm.application_priority import (
    DeterministicApplicationPriorityAssessor,
    extract_application_priority_level,
    format_application_priority_note,
    parse_application_priority_response,
)
from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.core.job_identity import PortalAwareJobIdentityStrategy
from job_hunter_agent.llm.job_requirements import (
    DeterministicJobRequirementsExtractor,
    JobRequirementSignals,
    extract_job_requirement_signals,
    format_job_requirement_signals,
    format_job_requirement_summary,
    parse_job_requirements_response,
)
from job_hunter_agent.infrastructure.repository import SqliteJobRepository
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
        self.repository.mark_status(saved[0].id, "approved", detail="Vaga aprovada: Senior Kotlin Engineer - ACME")
        self.repository.mark_status(saved[1].id, "rejected", detail="Vaga ignorada: Senior Kotlin Engineer - ACME")

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
        self.assertIn("T", run.started_at)
        self.assertIn("+00:00", run.started_at)
        self.assertIn("+00:00", row[4])

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

    def test_collection_cursor_defaults_to_first_page_and_persists_updates(self) -> None:
        self.assertEqual(
            self.repository.get_collection_cursor("LinkedIn", "https://example.com/search"),
            1,
        )

        self.repository.update_collection_cursor("LinkedIn", "https://example.com/search", 3)

        self.assertEqual(
            self.repository.get_collection_cursor("LinkedIn", "https://example.com/search"),
            3,
        )

    def test_mark_status_rejects_invalid_transition_value(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])

        with self.assertRaises(ValueError):
            self.repository.mark_status(saved[0].id, "archived")

    def test_job_events_track_collection_and_review_transitions(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]

        self.repository.mark_status(saved.id, "approved", detail="Vaga aprovada: Senior Kotlin Engineer - ACME")

        events = self.repository.list_job_events(saved.id)

        self.assertEqual(
            [event.event_type for event in events],
            ["status_changed", "job_collected"],
        )
        self.assertEqual(events[0].from_status, "collected")
        self.assertEqual(events[0].to_status, "approved")
        self.assertEqual(events[0].detail, "Vaga aprovada: Senior Kotlin Engineer - ACME")
        self.assertEqual(events[1].to_status, "collected")

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
            status="authorized_submit",
            notes="autorizado manualmente para envio",
        )
        self.repository.mark_application_status(
            application.id,
            status="submitted",
            submitted_at="2026-04-04T10:00:00",
        )

        stored = self.repository.get_application_by_job(saved.id)
        summary = self.repository.application_summary()

        self.assertEqual(stored.status, "submitted")
        self.assertEqual(stored.notes, "autorizado manualmente para envio")
        self.assertEqual(stored.last_preflight_detail, "")
        self.assertEqual(stored.last_submit_detail, "")
        self.assertEqual(stored.submitted_at, "2026-04-04T10:00:00")
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["authorized_submit"], 0)
        self.assertEqual(summary["submitted"], 1)

    def test_application_events_track_status_transitions(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]
        application = self.repository.create_application_draft(saved.id, notes="primeiro passo")

        self.repository.mark_application_status(
            application.id,
            status="ready_for_review",
            event_detail=f"Candidatura pronta para revisao: id={application.id}",
        )
        self.repository.mark_application_status(
            application.id,
            status="confirmed",
            event_detail=f"Candidatura confirmada: id={application.id}",
        )

        events = self.repository.list_application_events(application.id)

        self.assertEqual(
            [event.event_type for event in events],
            ["status_changed", "status_changed", "draft_created"],
        )
        self.assertEqual(events[0].from_status, "ready_for_review")
        self.assertEqual(events[0].to_status, "confirmed")
        self.assertEqual(events[0].detail, f"Candidatura confirmada: id={application.id}")
        self.assertEqual(events[1].from_status, "draft")
        self.assertEqual(events[1].to_status, "ready_for_review")
        self.assertEqual(events[1].detail, f"Candidatura pronta para revisao: id={application.id}")
        self.assertEqual(events[2].to_status, "draft")

    def test_record_application_event_persists_operational_detail(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]
        application = self.repository.create_application_draft(saved.id)

        self.repository.record_application_event(
            application.id,
            event_type="preflight_ready",
            detail="preflight real ok: CTA encontrado",
            from_status="confirmed",
            to_status="confirmed",
        )

        events = self.repository.list_application_events(application.id, limit=1)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "preflight_ready")
        self.assertIn("CTA encontrado", events[0].detail)
        self.assertEqual(events[0].from_status, "confirmed")
        self.assertEqual(events[0].to_status, "confirmed")

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

    def test_list_applications_with_jobs_by_status_returns_joined_rows(self) -> None:
        job = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]
        application = self.repository.create_application_draft(job.id, notes="contexto humano")
        self.repository.mark_application_status(application.id, status="confirmed")

        joined = self.repository.list_applications_with_jobs_by_status("confirmed")

        self.assertEqual(len(joined), 1)
        stored_application, stored_job = joined[0]
        self.assertEqual(stored_application.id, application.id)
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.id, job.id)

    def test_list_tracked_applications_with_jobs_limits_to_operational_statuses(self) -> None:
        first_job = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]
        second_job = self.repository.save_new_jobs([sample_job("https://example.com/job-2", "key-2")])[0]
        tracked = self.repository.create_application_draft(first_job.id)
        cancelled = self.repository.create_application_draft(second_job.id)
        self.repository.mark_application_status(tracked.id, status="authorized_submit")
        self.repository.mark_application_status(cancelled.id, status="cancelled")

        joined = self.repository.list_tracked_applications_with_jobs()

        self.assertEqual([application.id for application, _job in joined], [tracked.id])

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
        self.assertIn("rascunho criado apos aprovacao humana", stored.notes)
        self.assertIn("sinais estruturados:", stored.notes)
        self.assertEqual(stored.support_level, "manual_review")
        self.assertIsNone(self.repository.get_application_by_job(collected.id))

    def test_application_preparation_service_appends_structured_signals_to_notes(self) -> None:
        approved = self.repository.save_new_jobs([sample_job("https://example.com/job-1", "key-1")])[0]
        self.repository.mark_status(approved.id, "approved")

        service = ApplicationPreparationService(self.repository)

        drafts = service.create_drafts_for_approved_jobs(
            [approved.id],
            notes="rascunho criado apos aprovacao humana",
        )

        self.assertEqual(len(drafts), 1)
        self.assertIn("rascunho criado apos aprovacao humana", drafts[0].notes)
        self.assertIn("sinais estruturados:", drafts[0].notes)
        self.assertIn("prioridade sugerida:", drafts[0].notes)

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

    def test_deterministic_job_requirements_extractor_derives_basic_signals(self) -> None:
        extractor = DeterministicJobRequirementsExtractor()
        signals = extractor.extract(
            JobPosting(
                title="Desenvolvedor Java Senior",
                company="ACME",
                location="Brasil",
                work_mode="remoto",
                salary_text="Nao informado",
                url="https://example.com/job-1",
                source_site="LinkedIn",
                summary="Java com Spring Boot e AWS. Ingles avancado. Mentoria tecnica.",
                relevance=8,
                rationale="Boa aderencia",
                external_key="key-1",
            )
        )

        self.assertEqual(signals.seniority, "senior")
        self.assertIn("java", signals.primary_stack)
        self.assertIn("spring", signals.primary_stack)
        self.assertIn("aws", signals.secondary_stack)
        self.assertEqual(signals.english_level, "avancado")
        self.assertTrue(signals.leadership_signals)

    def test_parse_job_requirements_response_accepts_valid_json(self) -> None:
        signals = parse_job_requirements_response(
            '{"seniority":"pleno","primary_stack":["java","spring"],"secondary_stack":["aws"],"english_level":"intermediario","leadership_signals":false,"rationale":"sinais extraidos"}'
        )

        self.assertEqual(signals.seniority, "pleno")
        self.assertEqual(signals.primary_stack, ("java", "spring"))
        self.assertEqual(signals.secondary_stack, ("aws",))
        self.assertEqual(signals.english_level, "intermediario")
        self.assertFalse(signals.leadership_signals)

    def test_parse_job_requirements_response_falls_back_on_invalid_values(self) -> None:
        signals = parse_job_requirements_response('{"seniority":"guru","english_level":"x"}')

        self.assertEqual(signals.seniority, "nao_informada")
        self.assertEqual(signals.english_level, "nao_informado")

    def test_format_job_requirement_signals_is_concise(self) -> None:
        rendered = format_job_requirement_signals(
            JobRequirementSignals(
                seniority="pleno",
                primary_stack=("java", "spring"),
                secondary_stack=("aws",),
                english_level="intermediario",
                leadership_signals=False,
                rationale="sinais extraidos",
            )
        )

        self.assertIn("senioridade=pleno", rendered)
        self.assertIn("stack_principal=java, spring", rendered)
        self.assertIn("ingles=intermediario", rendered)

    def test_extract_job_requirement_signals_reads_structured_note(self) -> None:
        signals = extract_job_requirement_signals(
            "rascunho criado apos aprovacao humana\n"
            "sinais estruturados: senioridade=pleno; stack_principal=java, spring; "
            "stack_secundaria=aws; ingles=intermediario; lideranca=nao"
        )

        self.assertEqual(signals.seniority, "pleno")
        self.assertEqual(signals.primary_stack, ("java", "spring"))
        self.assertEqual(signals.secondary_stack, ("aws",))
        self.assertEqual(signals.english_level, "intermediario")
        self.assertFalse(signals.leadership_signals)

    def test_format_job_requirement_summary_is_operational(self) -> None:
        rendered = format_job_requirement_summary(
            JobRequirementSignals(
                seniority="senior",
                primary_stack=("java", "spring", "aws"),
                english_level="avancado",
                leadership_signals=True,
            )
        )

        self.assertIn("senioridade=senior", rendered)
        self.assertIn("stack=java, spring, aws", rendered)
        self.assertIn("ingles=avancado", rendered)
        self.assertIn("lideranca=sim", rendered)

    def test_parse_application_priority_response_accepts_valid_json(self) -> None:
        assessment = parse_application_priority_response(
            '{"level":"alta","rationale":"aderencia forte e modalidade favoravel"}'
        )

        self.assertEqual(assessment.level, "alta")
        self.assertEqual(assessment.rationale, "aderencia forte e modalidade favoravel")

    def test_parse_application_priority_response_rejects_invalid_level(self) -> None:
        assessment = parse_application_priority_response('{"level":"urgente"}')

        self.assertEqual(assessment.level, "baixa")
        self.assertIn("invalido", assessment.rationale)

    def test_format_and_extract_application_priority_note(self) -> None:
        note = format_application_priority_note(
            DeterministicApplicationPriorityAssessor().assess(sample_job("https://example.com/job-1", "key-1"))
        )

        self.assertIn("prioridade sugerida: alta", note)
        self.assertEqual(extract_application_priority_level(note), "alta")

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
            notes="contexto humano preservado",
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(application.id, status="confirmed")

        result = ApplicationPreflightService(self.repository).run_for_application(application.id)

        stored = self.repository.get_application(application.id)
        self.assertEqual(result.outcome, "ready")
        self.assertEqual(result.application_status, "confirmed")
        self.assertEqual(stored.status, "confirmed")
        self.assertEqual(stored.notes, "contexto humano preservado")
        self.assertIn("preflight ok", stored.last_preflight_detail)
        self.assertEqual(stored.last_error, "")
        latest_event = self.repository.list_application_events(application.id, limit=1)[0]
        self.assertEqual(latest_event.event_type, "preflight_ready")
        self.assertIn("preflight ok", latest_event.detail)

    def test_application_preflight_uses_real_flow_inspector_when_available(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://www.linkedin.com/jobs/view/123", "key-1")])[0]
        application = self.repository.create_application_draft(
            saved.id,
            notes="contexto humano preservado",
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(application.id, status="confirmed")

        class _Inspector:
            def __init__(self) -> None:
                self.called_with = []

            def inspect(self, job):
                self.called_with.append(job.url)
                return type("Inspection", (), {"outcome": "ready", "detail": "preflight real ok: CTA encontrado"})()

        inspector = _Inspector()
        result = ApplicationPreflightService(self.repository, flow_inspector=inspector).run_for_application(
            application.id
        )

        stored = self.repository.get_application(application.id)
        self.assertEqual(inspector.called_with, ["https://www.linkedin.com/jobs/view/123"])
        self.assertEqual(result.outcome, "ready")
        self.assertEqual(stored.status, "confirmed")
        self.assertEqual(stored.notes, "contexto humano preservado")
        self.assertIn("preflight real ok", stored.last_preflight_detail)
        latest_event = self.repository.list_application_events(application.id, limit=1)[0]
        self.assertEqual(latest_event.event_type, "preflight_ready")
        self.assertIn("preflight real ok", latest_event.detail)

    def test_preflight_preserves_support_snapshot(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://www.linkedin.com/jobs/view/123", "key-1")])[0]
        application = self.repository.create_application_draft(
            saved.id,
            support_level="manual_review",
            support_rationale="snapshot inicial de suporte",
        )
        self.repository.mark_application_status(application.id, status="confirmed")

        class _Inspector:
            def inspect(self, job):
                return type("Inspection", (), {"outcome": "ready", "detail": "preflight real ok: CTA encontrado"})()

        ApplicationPreflightService(self.repository, flow_inspector=_Inspector()).run_for_application(application.id)
        stored = self.repository.get_application(application.id)

        self.assertEqual(stored.support_level, "manual_review")
        self.assertEqual(stored.support_rationale, "snapshot inicial de suporte")

    def test_application_submission_requires_authorized_status(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://www.linkedin.com/jobs/view/123", "key-1")])[0]
        application = self.repository.create_application_draft(
            saved.id,
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(application.id, status="confirmed")

        result = ApplicationSubmissionService(self.repository).run_for_application(application.id)

        self.assertEqual(result.outcome, "ignored")
        self.assertEqual(result.application_status, "confirmed")
        self.assertIn("apenas para candidaturas autorizadas", result.detail)

    def test_application_submission_marks_submitted_when_applicant_succeeds(self) -> None:
        class _Applicant:
            def submit(self, application, job):
                from job_hunter_agent.application.contracts import ApplicationSubmissionResult

                return ApplicationSubmissionResult(
                    status="submitted",
                    detail="submissao real concluida",
                    submitted_at="2026-04-05T10:00:00",
                )

        saved = self.repository.save_new_jobs([sample_job("https://www.linkedin.com/jobs/view/123", "key-1")])[0]
        application = self.repository.create_application_draft(
            saved.id,
            notes="contexto humano preservado",
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(
            application.id,
            status="authorized_submit",
            last_preflight_detail="preflight real | pronto_para_envio=sim",
        )

        result = ApplicationSubmissionService(self.repository, applicant=_Applicant()).run_for_application(
            application.id
        )
        stored = self.repository.get_application(application.id)

        self.assertEqual(result.outcome, "submitted")
        self.assertEqual(result.application_status, "submitted")
        self.assertEqual(stored.status, "submitted")
        self.assertEqual(stored.submitted_at, "2026-04-05T10:00:00")
        self.assertEqual(stored.notes, "contexto humano preservado")
        self.assertIn("submissao real concluida", stored.last_submit_detail)
        latest_event = self.repository.list_application_events(application.id, limit=1)[0]
        self.assertEqual(latest_event.event_type, "submit_submitted")
        self.assertIn("submissao real concluida", latest_event.detail)

    def test_submit_preserves_support_snapshot(self) -> None:
        class _Applicant:
            def submit(self, application, job):
                from job_hunter_agent.application.contracts import ApplicationSubmissionResult

                return ApplicationSubmissionResult(
                    status="submitted",
                    detail="submissao real concluida",
                    submitted_at="2026-04-05T10:00:00",
                )

        saved = self.repository.save_new_jobs([sample_job("https://www.linkedin.com/jobs/view/123", "key-1")])[0]
        application = self.repository.create_application_draft(
            saved.id,
            support_level="manual_review",
            support_rationale="snapshot inicial de suporte",
        )
        self.repository.mark_application_status(
            application.id,
            status="authorized_submit",
            last_preflight_detail="preflight real | pronto_para_envio=sim",
        )

        ApplicationSubmissionService(self.repository, applicant=_Applicant()).run_for_application(application.id)
        stored = self.repository.get_application(application.id)

        self.assertEqual(stored.support_level, "manual_review")
        self.assertEqual(stored.support_rationale, "snapshot inicial de suporte")

    def test_application_submission_keeps_authorized_when_readiness_is_incomplete(self) -> None:
        class _Applicant:
            def submit(self, application, job):
                raise AssertionError("submit nao deveria ser chamado sem prontidao")

        saved = self.repository.save_new_jobs([sample_job("https://www.linkedin.com/jobs/view/123", "key-1")])[0]
        application = self.repository.create_application_draft(
            saved.id,
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(application.id, status="authorized_submit")

        readiness = ApplicationReadinessCheckService(
            linkedin_storage_state_path="./.nao-existe/linkedin-storage-state.json",
            resume_path="./curriculo-inexistente.pdf",
            contact_email="",
            phone="",
            phone_country_code="",
        )

        result = ApplicationSubmissionService(
            self.repository,
            applicant=_Applicant(),
            readiness_checker=readiness,
        ).run_for_application(application.id)
        stored = self.repository.get_application(application.id)

        self.assertEqual(result.outcome, "ignored")
        self.assertEqual(result.application_status, "authorized_submit")
        self.assertEqual(stored.status, "authorized_submit")
        self.assertIn("pronto_para_envio=sim", result.detail)

    def test_application_preflight_blocks_when_real_flow_inspector_blocks(self) -> None:
        saved = self.repository.save_new_jobs([sample_job("https://www.linkedin.com/jobs/view/123", "key-1")])[0]
        application = self.repository.create_application_draft(
            saved.id,
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(application.id, status="confirmed")

        class _Inspector:
            def inspect(self, job):
                return type(
                    "Inspection",
                    (),
                    {"outcome": "blocked", "detail": "preflight real bloqueado: CTA nao encontrado"},
                )()

        result = ApplicationPreflightService(self.repository, flow_inspector=_Inspector()).run_for_application(
            application.id
        )

        stored = self.repository.get_application(application.id)
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.application_status, "error_submit")
        self.assertEqual(stored.status, "error_submit")
        self.assertIn("CTA nao encontrado", stored.last_preflight_detail)
        self.assertIn("CTA nao encontrado", stored.last_error)

    def test_application_preflight_blocks_when_readiness_is_incomplete(self) -> None:
        class _Inspector:
            def inspect(self, job):
                raise AssertionError("preflight nao deveria inspecionar sem prontidao minima")

        saved = self.repository.save_new_jobs([sample_job("https://www.linkedin.com/jobs/view/123", "key-1")])[0]
        application = self.repository.create_application_draft(
            saved.id,
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(application.id, status="confirmed")

        readiness = ApplicationReadinessCheckService(
            linkedin_storage_state_path="./.nao-existe/linkedin-storage-state.json",
            resume_path="./curriculo-inexistente.pdf",
            contact_email="",
            phone="",
            phone_country_code="",
        )

        result = ApplicationPreflightService(
            self.repository,
            flow_inspector=_Inspector(),
            readiness_checker=readiness,
        ).run_for_application(application.id)

        stored = self.repository.get_application(application.id)
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.application_status, "error_submit")
        self.assertEqual(stored.status, "error_submit")
        self.assertIn("preflight bloqueado: prontidao operacional incompleta", result.detail)
        self.assertIn("--bootstrap-linkedin-session", result.detail)

    def test_application_preflight_blocks_for_portal_without_preflight_support(self) -> None:
        gupy_job = sample_job("https://empresa.gupy.io/job/123", "key-1")
        gupy_job = JobPosting(**{**gupy_job.__dict__, "source_site": "Gupy"})
        saved = self.repository.save_new_jobs([gupy_job])[0]
        application = self.repository.create_application_draft(
            saved.id,
            support_level="manual_review",
            support_rationale="portal externo ainda exige revisao manual",
        )
        self.repository.mark_application_status(application.id, status="confirmed")

        result = ApplicationPreflightService(self.repository).run_for_application(application.id)

        stored = self.repository.get_application(application.id)
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.application_status, "error_submit")
        self.assertEqual(stored.status, "error_submit")
        self.assertIn("portal Gupy ainda nao possui preflight suportado", stored.last_error)

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
        self.assertIn("nao suportado", stored.last_preflight_detail)
        self.assertIn("nao suportado", stored.last_error)
