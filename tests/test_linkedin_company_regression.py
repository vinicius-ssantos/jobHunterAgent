from unittest import TestCase

from job_hunter_agent.collectors.linkedin import clean_linkedin_company


class LinkedInCompanyRegressionTests(TestCase):
    def test_clean_linkedin_company_rejects_location_fragment_with_trailing_comma(self) -> None:
        self.assertEqual(clean_linkedin_company("Taboão da Serra,"), "")
        self.assertEqual(clean_linkedin_company("Taboao da Serra,"), "")

    def test_clean_linkedin_company_rejects_short_role_fragment(self) -> None:
        self.assertEqual(clean_linkedin_company("Analista e"), "")
