from unittest import TestCase

from job_hunter_agent.application.application_readiness import ApplicationReadinessCheckService
from job_hunter_agent.core.domain import JobPosting


def _sample_linkedin_job() -> JobPosting:
    return JobPosting(
        id=1,
        title="Backend Java",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url="https://www.linkedin.com/jobs/view/123/",
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia",
        external_key="key-1",
    )


class ApplicationReadinessCheckServiceTests(TestCase):
    def test_check_preflight_ready_reports_missing_authenticated_session(self) -> None:
        service = ApplicationReadinessCheckService(
            linkedin_storage_state_path="./.nao-existe/linkedin-storage-state.json",
            resume_path="./curriculo-inexistente.pdf",
            contact_email="",
            phone="",
            phone_country_code="",
        )

        readiness = service.check_preflight_ready(_sample_linkedin_job())

        self.assertFalse(readiness.ok)
        self.assertEqual(len(readiness.failures), 1)
        self.assertIn("sessao autenticada do LinkedIn nao encontrada", readiness.failures[0])
        self.assertIn("--bootstrap-linkedin-session", readiness.failures[0])

    def test_check_submit_ready_reports_missing_local_prerequisites(self) -> None:
        service = ApplicationReadinessCheckService(
            linkedin_storage_state_path="./.nao-existe/linkedin-storage-state.json",
            resume_path="./curriculo-inexistente.pdf",
            contact_email="",
            phone="",
            phone_country_code="",
        )

        readiness = service.check_submit_ready(_sample_linkedin_job())

        self.assertFalse(readiness.ok)
        self.assertTrue(any("sessao autenticada do LinkedIn nao encontrada" in item for item in readiness.failures))
        self.assertTrue(any("curriculo configurado nao foi encontrado" in item for item in readiness.failures))
        self.assertIn(
            "email de contato nao configurado (JOB_HUNTER_APPLICATION_CONTACT_EMAIL)",
            readiness.failures,
        )
        self.assertIn(
            "telefone de contato nao configurado (JOB_HUNTER_APPLICATION_PHONE)",
            readiness.failures,
        )
        self.assertIn(
            "codigo do pais do telefone nao configurado (JOB_HUNTER_APPLICATION_PHONE_COUNTRY_CODE)",
            readiness.failures,
        )

    def test_check_submit_ready_reports_invalid_contact_data(self) -> None:
        service = ApplicationReadinessCheckService(
            linkedin_storage_state_path="./.nao-existe/linkedin-storage-state.json",
            resume_path="./curriculo-inexistente.pdf",
            contact_email="vinicius-at-example.com",
            phone="1234",
            phone_country_code="Brasil",
        )

        readiness = service.check_submit_ready(_sample_linkedin_job())

        self.assertFalse(readiness.ok)
        self.assertIn(
            "email de contato invalido (JOB_HUNTER_APPLICATION_CONTACT_EMAIL)",
            readiness.failures,
        )
        self.assertIn(
            "telefone de contato invalido (JOB_HUNTER_APPLICATION_PHONE)",
            readiness.failures,
        )
        self.assertIn(
            "codigo do pais do telefone invalido (JOB_HUNTER_APPLICATION_PHONE_COUNTRY_CODE)",
            readiness.failures,
        )
