import unittest
from pathlib import Path

from job_hunter_agent.application.application_cli_rendering import (
    render_application_detail,
    render_application_events,
    render_application_list,
    render_execution_summary,
    render_failure_artifacts,
    render_job_detail,
    render_job_list,
    render_operations_report,
    render_status_overview,
    summarize_operational_counts,
)
from job_hunter_agent.core.domain import JobApplication, JobApplicationEvent, JobPosting


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


class ApplicationCliRenderingTests(unittest.TestCase):
    def test_render_application_list_uses_operational_reason(self) -> None:
        application = JobApplication(
            id=2,
            job_id=10,
            status="confirmed",
            support_level="manual_review",
            last_preflight_detail="preflight real inconclusivo | perguntas_pendentes=ha quantos anos voce usa java?",
        )

        rendered = render_application_list(
            applications_with_jobs=[(application, _sample_job(job_id=10, status="approved"))],
            status="confirmed",
        )

        self.assertIn("Candidaturas listadas: 1", rendered)
        self.assertIn("Backend Java | ACME", rendered)
        self.assertIn("op=perguntas_adicionais", rendered)

    def test_render_job_list_supports_empty_filter(self) -> None:
        rendered = render_job_list(jobs=[], status="approved")

        self.assertEqual(rendered, "Nenhuma vaga encontrada para status=approved.")

    def test_render_job_detail_includes_events(self) -> None:
        event = type(
            "Event",
            (),
            {
                "created_at": "2026-04-07T12:00:00",
                "event_type": "status_changed",
                "from_status": "collected",
                "to_status": "approved",
                "detail": "Vaga aprovada: Backend Java - ACME",
            },
        )()

        rendered = render_job_detail(
            job=_sample_job(job_id=10, status="approved"),
            application=JobApplication(id=4, job_id=10, status="confirmed", support_level="manual_review"),
            events=[event],
        )

        self.assertIn("application_id=4", rendered)
        self.assertIn("eventos_recentes:", rendered)
        self.assertIn("status_changed", rendered)

    def test_summarize_operational_counts_ignores_unclassified(self) -> None:
        counts = summarize_operational_counts(
            applications=[
                JobApplication(
                    id=1,
                    job_id=10,
                    status="authorized_submit",
                    support_level="manual_review",
                    last_preflight_detail="preflight real | pronto_para_envio=sim | ok: fluxo pronto para submissao assistida no LinkedIn",
                ),
                JobApplication(id=2, job_id=11, status="draft", support_level="manual_review"),
            ]
        )

        self.assertEqual(counts, {"pronto_para_envio": 1})

    def test_render_status_overview_renders_operational_section(self) -> None:
        rendered = render_status_overview(
            job_summary={"total": 1, "collected": 0, "approved": 1, "rejected": 0, "error_collect": 0},
            application_summary={
                "total": 1,
                "draft": 0,
                "ready_for_review": 0,
                "confirmed": 1,
                "authorized_submit": 0,
                "submitted": 0,
                "error_submit": 0,
                "cancelled": 0,
            },
            operational_counts={"similar_jobs": 1},
        )

        self.assertIn("Resumo operacional:", rendered)
        self.assertIn("- approved=1", rendered)
        self.assertIn("- similar_jobs=1", rendered)

    def test_render_operations_report_combines_snapshot_and_window(self) -> None:
        events = [
            JobApplicationEvent(
                id=1,
                application_id=3,
                event_type="preflight_blocked",
                detail="readiness=no_apply_cta | motivo=a vaga so oferece candidatura externa no site da empresa",
                created_at="2026-05-01T10:00:00",
            )
        ]

        rendered = render_operations_report(
            since="2026-05-01T00:00:00+00:00",
            job_summary={"total": 2, "collected": 1, "approved": 1, "rejected": 0, "error_collect": 0},
            application_summary={
                "total": 1,
                "draft": 0,
                "ready_for_review": 0,
                "confirmed": 1,
                "authorized_submit": 0,
                "submitted": 0,
                "error_submit": 0,
                "cancelled": 0,
            },
            operational_counts={"candidatura_externa": 1},
            events=events,
        )

        self.assertIn("Relatorio operacional local:", rendered)
        self.assertIn("janela_desde=2026-05-01T00:00:00+00:00", rendered)
        self.assertIn("snapshot_atual:", rendered)
        self.assertIn("resumo_da_janela:", rendered)
        self.assertIn("candidatura_externa=1", rendered)
        self.assertIn("eventos_recentes:", rendered)
        self.assertIn("preflight_blocked", rendered)

    def test_render_application_events_handles_empty(self) -> None:
        rendered = render_application_events(application_id=2, events=[])

        self.assertEqual(rendered, "Nenhum evento encontrado para candidatura: id=2")

    def test_render_application_detail_includes_classification(self) -> None:
        application = JobApplication(
            id=2,
            job_id=10,
            status="confirmed",
            support_level="manual_review",
            notes="contexto humano",
            last_preflight_detail="preflight real ok",
            last_submit_detail="submissao ainda nao executada",
        )

        rendered = render_application_detail(
            application=application,
            job=_sample_job(job_id=10, status="approved"),
            events=[],
        )

        self.assertIn("classificacao_operacional=", rendered)
        self.assertIn("last_preflight_detail=preflight real ok", rendered)
        self.assertIn("manual_review_detail=revisao_humana=necessaria", rendered)

    def test_render_failure_artifacts_handles_missing_directory(self) -> None:
        rendered = render_failure_artifacts(
            artifacts_dir=Path("diretorio-inexistente"),
            files=[],
            limit=5,
        )

        self.assertEqual(rendered, "Nenhum diretorio de artefatos encontrado: diretorio-inexistente")

    def test_render_execution_summary_groups_block_types(self) -> None:
        events = [
            JobApplicationEvent(
                id=1,
                application_id=1,
                event_type="preflight_blocked",
                detail="readiness=no_apply_cta | motivo=a vaga so oferece candidatura externa no site da empresa",
                created_at="2026-04-08T10:01:00",
            ),
            JobApplicationEvent(
                id=2,
                application_id=2,
                event_type="submit_error",
                detail="readiness=listing_redirect | motivo=a navegacao caiu em listagem ou colecao do LinkedIn | pagina=https://www.linkedin.com/jobs/collections/similar-jobs/",
                created_at="2026-04-08T10:02:00",
            ),
            JobApplicationEvent(
                id=3,
                application_id=2,
                event_type="status_changed",
                from_status="draft",
                to_status="ready_for_review",
                detail="Candidatura pronta para revisao",
                created_at="2026-04-08T10:03:00",
            ),
            JobApplicationEvent(
                id=4,
                application_id=2,
                event_type="status_changed",
                from_status="ready_for_review",
                to_status="confirmed",
                detail="Candidatura confirmada",
                created_at="2026-04-08T10:04:00",
            ),
            JobApplicationEvent(
                id=5,
                application_id=2,
                event_type="status_changed",
                from_status="confirmed",
                to_status="authorized_submit",
                detail="Candidatura autorizada",
                created_at="2026-04-08T10:05:00",
            ),
            JobApplicationEvent(
                id=6,
                application_id=2,
                event_type="status_changed",
                from_status="authorized_submit",
                to_status="submitted",
                detail="Candidatura enviada",
                created_at="2026-04-08T10:06:00",
            ),
        ]

        rendered = render_execution_summary(events=events)

        self.assertIn("- preflights_concluidos=1", rendered)
        self.assertIn("- submits_concluidos=1", rendered)
        self.assertIn("candidatura_externa=1", rendered)
        self.assertIn("similar_jobs=1", rendered)
        self.assertIn("draft_para_ready_for_review=1", rendered)
        self.assertIn("ready_for_review_para_confirmed=1", rendered)
        self.assertIn("confirmed_para_authorized_submit=1", rendered)
        self.assertIn("authorized_submit_para_submitted=1", rendered)
        self.assertIn("taxa_authorized_submit_para_submitted=100.0%", rendered)
