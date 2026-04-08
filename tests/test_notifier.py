import shutil
from unittest import TestCase

from job_hunter_agent.core.domain import JobApplication, JobPosting
from job_hunter_agent.infrastructure.notifier import (
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
    resolve_application_submit_request,
)
from job_hunter_agent.infrastructure.notifier_rendering import (
    summarize_application_notes,
    summarize_application_operation,
    summarize_operational_classifications,
)
from job_hunter_agent.infrastructure.repository import SqliteJobRepository
from job_hunter_agent.llm.review_rationale import (
    StructuredReviewRationale,
    parse_structured_review_rationale,
    render_review_rationale,
)
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

    def test_build_job_card_message_accepts_structured_rationale(self) -> None:
        message = build_job_card_message(
            sample_job(),
            StructuredReviewRationale(
                strengths=("stack aderente",),
                concerns=("senioridade incerta",),
                risk="detalhes insuficientes",
            ),
        )

        self.assertIn("Pontos a favor:", message)
        self.assertIn("- stack aderente", message)
        self.assertIn("Pontos contra:", message)
        self.assertIn("Risco principal: detalhes insuficientes", message)

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
                notes="prioridade sugerida: alta | motivo: aderencia forte",
                support_level="manual_review",
                support_rationale="linkedin interno ainda requer confirmacao",
            )

            line = build_application_preview_line(repository, draft)

            self.assertIn("Senior Kotlin Engineer", line)
            self.assertIn("[draft | manual_review | prioridade alta | op=sem_detalhe_operacional]", line)
            self.assertIn("manual_review", line)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_resolve_application_action_happy_path(self) -> None:
        from job_hunter_agent.core.domain import JobApplication

        draft = JobApplication(id=10, job_id=1, status="draft")
        ready = JobApplication(id=10, job_id=1, status="ready_for_review")
        confirmed = JobApplication(id=10, job_id=1, status="confirmed")
        errored = JobApplication(id=13, job_id=1, status="error_submit")

        self.assertEqual(resolve_application_action(draft, "app_prepare")[0], "ready_for_review")
        self.assertEqual(resolve_application_action(ready, "app_confirm")[0], "confirmed")
        self.assertEqual(resolve_application_action(ready, "app_cancel")[0], "cancelled")
        self.assertEqual(resolve_application_action(confirmed, "app_authorize")[0], "authorized_submit")
        self.assertEqual(resolve_application_action(errored, "app_authorize")[0], "authorized_submit")

    def test_resolve_application_action_is_idempotent(self) -> None:
        from job_hunter_agent.core.domain import JobApplication

        confirmed = JobApplication(id=10, job_id=1, status="confirmed")
        authorized = JobApplication(id=12, job_id=1, status="authorized_submit")
        cancelled = JobApplication(id=11, job_id=1, status="cancelled")
        errored = JobApplication(id=13, job_id=1, status="error_submit")

        self.assertIsNone(resolve_application_action(confirmed, "app_confirm")[0])
        self.assertIsNone(resolve_application_action(authorized, "app_authorize")[0])
        self.assertIsNone(resolve_application_action(cancelled, "app_cancel")[0])
        self.assertIsNone(resolve_application_action(errored, "app_confirm")[0])

    def test_build_application_action_rows_varies_by_status(self) -> None:
        from job_hunter_agent.core.domain import JobApplication

        def button(label: str, callback_data: str) -> tuple[str, str]:
            return (label, callback_data)

        draft_rows = build_application_action_rows(JobApplication(id=1, job_id=1, status="draft"), button)
        ready_rows = build_application_action_rows(JobApplication(id=1, job_id=1, status="ready_for_review"), button)
        confirmed_rows = build_application_action_rows(JobApplication(id=1, job_id=1, status="confirmed"), button)
        authorized_rows = build_application_action_rows(JobApplication(id=1, job_id=1, status="authorized_submit"), button)
        errored_rows = build_application_action_rows(JobApplication(id=1, job_id=1, status="error_submit"), button)

        self.assertEqual(draft_rows[0][0], ("Preparar", "app_prepare:1"))
        self.assertEqual(ready_rows[0][0], ("Confirmar", "app_confirm:1"))
        self.assertEqual(confirmed_rows[0][0], ("Validar fluxo", "app_preflight:1"))
        self.assertEqual(confirmed_rows[0][1], ("Autorizar envio", "app_authorize:1"))
        self.assertEqual(authorized_rows[0][0], ("Enviar candidatura", "app_submit:1"))
        self.assertEqual(authorized_rows[0][1], ("Cancelar", "app_cancel:1"))
        self.assertEqual(errored_rows[0][0], ("Validar fluxo", "app_preflight:1"))
        self.assertEqual(errored_rows[0][1], ("Reautorizar", "app_authorize:1"))

    def test_resolve_application_preflight_request_requires_confirmed_status(self) -> None:
        from job_hunter_agent.core.domain import JobApplication

        confirmed = JobApplication(id=1, job_id=1, status="confirmed")
        authorized = JobApplication(id=3, job_id=3, status="authorized_submit")
        draft = JobApplication(id=2, job_id=2, status="draft")
        errored = JobApplication(id=4, job_id=4, status="error_submit")

        self.assertEqual(resolve_application_preflight_request(confirmed), (True, "Executando preflight da candidatura: id=1"))
        self.assertEqual(
            resolve_application_preflight_request(errored),
            (True, "Executando novo preflight da candidatura apos erro de envio: id=4"),
        )
        self.assertEqual(
            resolve_application_preflight_request(authorized),
            (False, "Candidatura ja foi autorizada para envio: id=3"),
        )
        self.assertEqual(
            resolve_application_preflight_request(draft),
            (False, "Candidatura ainda nao foi confirmada para preflight: id=2"),
        )

    def test_resolve_application_submit_request_requires_authorized_status(self) -> None:
        from job_hunter_agent.core.domain import JobApplication

        authorized = JobApplication(id=1, job_id=1, status="authorized_submit")
        confirmed = JobApplication(id=2, job_id=2, status="confirmed")
        submitted = JobApplication(id=3, job_id=3, status="submitted")

        self.assertEqual(
            resolve_application_submit_request(authorized),
            (True, "Executando submissao real da candidatura: id=1"),
        )
        self.assertEqual(
            resolve_application_submit_request(confirmed),
            (False, "Candidatura ainda nao foi autorizada para envio: id=2"),
        )
        self.assertEqual(
            resolve_application_submit_request(submitted),
            (False, "Candidatura ja foi enviada: id=3"),
        )

    def test_parse_structured_review_rationale_accepts_valid_json(self) -> None:
        structured = parse_structured_review_rationale(
            '{"strengths":["stack aderente"],"concerns":["senioridade incerta"],"risk":"detalhes insuficientes"}'
        )

        self.assertEqual(structured.strengths, ("stack aderente",))
        self.assertEqual(structured.concerns, ("senioridade incerta",))
        self.assertEqual(structured.risk, "detalhes insuficientes")

    def test_render_review_rationale_falls_back_to_raw_text(self) -> None:
        rendered = render_review_rationale(sample_job())

        self.assertEqual(rendered, "Boa aderencia ao perfil.")


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
        second_job = self.repository.save_new_jobs(
            [
                JobPosting(
                    title="Backend Java Retry",
                    company="OMEGA",
                    location="Brasil",
                    work_mode="remoto",
                    salary_text="Nao informado",
                    url="https://example.com/job-retry",
                    source_site="LinkedIn",
                    summary="Resumo",
                    relevance=7,
                    rationale="Boa aderencia",
                    external_key="key-retry",
                    status="approved",
                )
            ]
        )[0]
        self.repository.mark_status(approved_job.id, "approved")
        self.repository.mark_status(second_job.id, "approved")
        application = self.repository.create_application_draft(
            approved_job.id,
            notes="rascunho criado apos aprovacao humana\nprioridade sugerida: alta | motivo: aderencia forte",
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(application.id, status="authorized_submit")
        errored = self.repository.create_application_draft(
            second_job.id,
            notes="prioridade sugerida: baixa | motivo: erro anterior",
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(errored.id, status="error_submit")

        message = build_application_queue_message(self.repository)

        self.assertIn("Candidaturas:", message)
        self.assertIn("Autorizadas para envio: 1", message)
        self.assertIn("Com erro: 1", message)
        self.assertIn("Senior Kotlin Engineer - ACME [authorized_submit | manual_review | prioridade alta | op=sem_detalhe_operacional]", message)

    def test_build_application_queue_message_orders_by_priority(self) -> None:
        first_job = self.repository.save_new_jobs([sample_job(status="approved")])[0]
        second_job = self.repository.save_new_jobs(
            [
                JobPosting(
                    title="Backend Java Pleno",
                    company="BETA",
                    location="Brasil",
                    work_mode="hibrido",
                    salary_text="Nao informado",
                    url="https://example.com/job-2",
                    source_site="LinkedIn",
                    summary="Resumo",
                    relevance=7,
                    rationale="Boa aderencia",
                    external_key="key-2",
                    status="approved",
                )
            ]
        )[0]
        self.repository.mark_status(first_job.id, "approved")
        self.repository.mark_status(second_job.id, "approved")
        self.repository.create_application_draft(
            first_job.id,
            notes="prioridade sugerida: baixa | motivo: revisar depois",
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.create_application_draft(
            second_job.id,
            notes="prioridade sugerida: alta | motivo: revisar primeiro",
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )

        message = build_application_queue_message(self.repository)
        beta_index = message.index("Backend Java Pleno - BETA")
        acme_index = message.index("Senior Kotlin Engineer - ACME")

        self.assertLess(beta_index, acme_index)

    def test_build_application_card_message_contains_support_and_notes(self) -> None:
        approved_job = self.repository.save_new_jobs([sample_job(status="approved")])[0]
        self.repository.mark_status(approved_job.id, "approved")
        application = self.repository.create_application_draft(
            approved_job.id,
            notes=(
                "rascunho criado apos aprovacao humana\n"
                "sinais estruturados: senioridade=senior; stack_principal=java, spring; "
                "stack_secundaria=aws; ingles=avancado; lideranca=sim\n"
                "prioridade sugerida: media | motivo: revisar em seguida"
            ),
            support_level="manual_review",
            support_rationale="linkedin interno ainda requer confirmacao",
        )
        self.repository.mark_application_status(
            application.id,
            status="confirmed",
            last_preflight_detail="preflight real ok: CTA encontrado",
        )
        application = self.repository.get_application(application.id)

        message = build_application_card_message(self.repository, application)

        self.assertIn("Candidatura", message)
        self.assertIn("Vaga: Senior Kotlin Engineer", message)
        self.assertIn("Suporte: manual_review", message)
        self.assertIn("Classificacao operacional: manual_review | cta detectado; validar fluxo", message)
        self.assertIn("Prioridade: media", message)
        self.assertIn("Sinais: senioridade=senior | stack=java, spring | ingles=avancado | lideranca=sim", message)
        self.assertIn("Contexto: rascunho criado apos aprovacao humana", message)
        self.assertIn("Operacao: Preflight: preflight real ok: CTA encontrado", message)

    def test_summarize_operational_classifications_counts_known_variants(self) -> None:
        summary = summarize_operational_classifications(
            [
                JobApplication(
                    id=1,
                    job_id=1,
                    status="authorized_submit",
                    last_preflight_detail="preflight real | pronto_para_envio=sim | ok: fluxo pronto para submissao assistida no LinkedIn",
                ),
                JobApplication(
                    id=2,
                    job_id=2,
                    status="error_submit",
                    last_error="readiness=listing_redirect | motivo=a navegacao caiu em listagem ou colecao do LinkedIn | pagina=https://www.linkedin.com/jobs/collections/similar-jobs/",
                ),
                JobApplication(
                    id=3,
                    job_id=3,
                    status="error_submit",
                    last_error="submissao real bloqueada | bloqueio=perguntas_obrigatorias | perguntas_pendentes=ha quantos anos voce usa java?",
                ),
            ]
        )

        self.assertIn("- pronto_para_envio=1", summary)
        self.assertIn("- similar_jobs=1", summary)
        self.assertIn("- perguntas_adicionais=1", summary)

    def test_summarize_application_notes_prefers_human_context_lines(self) -> None:
        notes = (
            "rascunho criado apos aprovacao humana\n"
            "linha irrelevante antiga\n"
            "sinais estruturados: senioridade=senior; stack_principal=java, spring\n"
            "prioridade sugerida: alta | motivo: revisar primeiro\n"
        )

        summary = summarize_application_notes(notes, max_chars=220)

        self.assertIn("rascunho criado apos aprovacao humana", summary)
        self.assertIn("prioridade sugerida: alta", summary)
        self.assertNotIn("linha irrelevante antiga", summary)

    def test_summarize_application_operation_prefers_explicit_state_fields(self) -> None:
        summary = summarize_application_operation(
            application=type(
                "_Application",
                (),
                {
                    "last_preflight_detail": "preflight real ok: CTA encontrado",
                    "last_submit_detail": "submissao real concluida no LinkedIn",
                    "last_error": "",
                },
            )(),
            max_chars=220,
        )

        self.assertIn("Preflight: preflight real ok: CTA encontrado", summary)
        self.assertIn("Submit: submissao real concluida no LinkedIn", summary)
