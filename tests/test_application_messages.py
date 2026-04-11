import unittest

from job_hunter_agent.application.application_messages import (
    format_created_application_draft,
    format_existing_application_for_job,
    format_linkedin_preflight_ready,
    format_preflight_cli_result,
    format_preflight_inspection_error,
    format_submit_cli_result,
    format_submit_detail,
    format_submit_readiness_incomplete,
)
from job_hunter_agent.core.domain import JobApplication


class ApplicationMessagesTests(unittest.TestCase):
    def test_format_preflight_cli_result_renders_status(self) -> None:
        rendered = format_preflight_cli_result(
            detail="preflight ok",
            application_status="confirmed",
        )

        self.assertEqual(rendered, "Preflight: preflight ok (status=confirmed)")

    def test_format_submit_cli_result_renders_status(self) -> None:
        rendered = format_submit_cli_result(
            detail="submissao concluida",
            application_status="submitted",
        )

        self.assertEqual(rendered, "Submissao: submissao concluida (status=submitted)")

    def test_format_submit_readiness_incomplete_includes_failures(self) -> None:
        rendered = format_submit_readiness_incomplete(
            failures=["curriculo ausente", "telefone ausente"],
        )

        self.assertEqual(
            rendered,
            "submissao real bloqueada: prontidao operacional incompleta | "
            "faltando=curriculo ausente; telefone ausente",
        )

    def test_format_submit_detail_appends_external_reference(self) -> None:
        rendered = format_submit_detail(
            detail="submissao real concluida",
            external_reference="abc-123",
        )

        self.assertEqual(rendered, "submissao real concluida | referencia=abc-123")

    def test_format_linkedin_preflight_ready_supports_manual_review_snapshot(self) -> None:
        rendered = format_linkedin_preflight_ready(support_level="manual_review")

        self.assertEqual(
            rendered,
            "preflight ok: vaga interna do LinkedIn pronta para futura automacao assistida",
        )

    def test_format_preflight_inspection_error_keeps_exception_message(self) -> None:
        rendered = format_preflight_inspection_error(RuntimeError("portal indisponivel"))

        self.assertEqual(
            rendered,
            "preflight real falhou ao inspecionar a pagina: portal indisponivel",
        )

    def test_format_existing_application_for_job_renders_compact_reference(self) -> None:
        application = JobApplication(
            id=21,
            job_id=10,
            status="confirmed",
            support_level="manual_review",
        )

        rendered = format_existing_application_for_job(application=application, job_id=10)

        self.assertEqual(
            rendered,
            "Candidatura ja existe para a vaga: application_id=21 status=confirmed job_id=10",
        )

    def test_format_created_application_draft_renders_support_level(self) -> None:
        rendered = format_created_application_draft(
            application_id=9,
            job_id=10,
            status="draft",
            support_level="auto_supported",
        )

        self.assertEqual(
            rendered,
            "Rascunho criado: application_id=9 job_id=10 status=draft suporte=auto_supported",
        )
