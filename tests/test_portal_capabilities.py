from unittest import TestCase

from job_hunter_agent.core.domain import JobPosting
from job_hunter_agent.core.portal_capabilities import get_portal_capabilities


def _sample_job(url: str, site: str) -> JobPosting:
    return JobPosting(
        id=1,
        title="Backend Java",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url=url,
        source_site=site,
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia",
        external_key="key-1",
    )


class PortalCapabilitiesTests(TestCase):
    def test_get_portal_capabilities_for_linkedin_internal_job(self) -> None:
        capabilities = get_portal_capabilities(_sample_job("https://www.linkedin.com/jobs/view/123/", "LinkedIn"))

        self.assertEqual(capabilities.portal_name, "LinkedIn")
        self.assertTrue(capabilities.collect_supported)
        self.assertTrue(capabilities.preflight_supported)
        self.assertTrue(capabilities.submit_supported)
        self.assertTrue(capabilities.requires_login)
        self.assertTrue(capabilities.supports_easy_apply)
        self.assertTrue(capabilities.supports_failure_artifacts)

    def test_get_portal_capabilities_for_non_linkedin_job(self) -> None:
        capabilities = get_portal_capabilities(_sample_job("https://empresa.gupy.io/job/123", "Gupy"))

        self.assertEqual(capabilities.portal_name, "Gupy")
        self.assertTrue(capabilities.collect_supported)
        self.assertFalse(capabilities.preflight_supported)
        self.assertFalse(capabilities.submit_supported)
