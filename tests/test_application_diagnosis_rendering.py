from unittest import TestCase

from job_hunter_agent.application.application_cli_rendering import render_application_diagnosis
from job_hunter_agent.core.domain import JobApplication, JobApplicationEvent, JobPosting
from job_hunter_agent.core.events import ApplicationBlockedV1


def _sample_job(*, job_id: int = 10) -> JobPosting:
    return JobPosting(
        id=job_id,
        title="Backend Java",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url="https://example.com/job",
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia",
        external_key="linkedin-10",
        status="approved",
    )


class ApplicationDiagnosisRenderingTests(TestCase):
    def test_render_application_diagnosis_includes_aggregate_sections_and_next_action(self) -> None:
        application = JobApplication(
            id=32,
            job_id=10,
            status="error_submit",
            support_level="manual_review",
            last_preflight_detail="preflight real ok",
            last_submit_detail="submit interrompido",
            last_error="readiness=listing_redirect | motivo=a navegacao caiu em listagem",
            notes="revisar antes de retentar",
        )
        sqlite_event = JobApplicationEvent(
            id=1,
            application_id=32,
            event_type="submit_error",
            from_status="authorized_submit",
            to_status="error_submit",
            detail="submit falhou",
            created_at="2026-04-27T10:00:00",
        )
        domain_event = ApplicationBlockedV1(
            application_id=32,
            job_id=10,
            reason="listing_redirect",
            detail="navegacao caiu em listagem",
            retryable=True,
            occurred_at="2026-04-27T10:01:00+00:00",
            correlation_id="application:32",
        )

        rendered = render_application_diagnosis(
            application=application,
            job=_sample_job(),
            events=[sqlite_event],
            domain_events=(domain_event,),
            domain_events_enabled=True,
        )

        self.assertIn("Diagnostico da candidatura 32", rendered)
        self.assertIn("candidatura:", rendered)
        self.assertIn("vaga:", rendered)
        self.assertIn("preflight_submit:", rendered)
        self.assertIn("last_preflight_detail=preflight real ok", rendered)
        self.assertIn("last_submit_detail=submit interrompido", rendered)
        self.assertIn("last_error=readiness=listing_redirect", rendered)
        self.assertIn("proxima_acao:", rendered)
        self.assertIn("investigar bloqueio", rendered)
        self.assertIn("eventos_sqlite_recentes:", rendered)
        self.assertIn("submit_error", rendered)
        self.assertIn("domain_events_recentes:", rendered)
        self.assertIn("ApplicationBlockedV1", rendered)
        self.assertIn("correlation_id=application:32", rendered)
        self.assertIn("retryable=True", rendered)

    def test_render_application_diagnosis_reports_disabled_domain_events(self) -> None:
        application = JobApplication(id=33, job_id=11, status="draft", support_level="manual_review")

        rendered = render_application_diagnosis(
            application=application,
            job=None,
            events=[],
            domain_events=(),
            domain_events_enabled=False,
        )

        self.assertIn("vaga nao encontrada", rendered)
        self.assertIn("preparar revisao: python main.py applications prepare --id 33", rendered)
        self.assertIn("eventos_sqlite_recentes:\n- nenhum", rendered)
        self.assertIn("domain_events_recentes:\n- indisponivel_ou_desabilitado", rendered)
