from unittest import TestCase

from job_hunter_agent.core.job_identity import (
    JobTextIdentity,
    PortalAwareJobIdentityStrategy,
    normalize_identity_text,
    normalize_job_url,
)


class JobIdentityTests(TestCase):
    def test_normalize_job_url_removes_volatile_linkedin_parameters(self) -> None:
        url = (
            "https://www.linkedin.com/jobs/view/1234567890/?"
            "currentJobId=1234567890&position=1&trk=public_jobs_jserp-result_search-card"
            "&utm_source=newsletter&foo=bar#details"
        )

        self.assertEqual(
            normalize_job_url(url),
            "https://linkedin.com/jobs/view/1234567890?foo=bar",
        )

    def test_url_lookup_patterns_include_raw_normalized_and_linkedin_id_patterns(self) -> None:
        strategy = PortalAwareJobIdentityStrategy()

        patterns = strategy.url_lookup_patterns(
            "https://www.linkedin.com/jobs/view/1234567890/?trk=public_jobs&position=2"
        )

        self.assertIn(
            "https://www.linkedin.com/jobs/view/1234567890/?trk=public_jobs&position=2",
            patterns,
        )
        self.assertIn("https://linkedin.com/jobs/view/1234567890", patterns)
        self.assertIn("%/jobs/view/1234567890%", patterns)

    def test_url_lookup_patterns_include_current_job_id_pattern(self) -> None:
        strategy = PortalAwareJobIdentityStrategy()

        patterns = strategy.url_lookup_patterns(
            "https://www.linkedin.com/jobs/search/?currentJobId=9876543210&start=25&trk=jobs_jserp"
        )

        self.assertIn("https://linkedin.com/jobs/search", patterns)
        self.assertIn("%/jobs/view/9876543210%", patterns)

    def test_normalize_identity_text_collapses_spacing_case_and_accents(self) -> None:
        self.assertEqual(normalize_identity_text("  São   PAULO  "), "sao paulo")

    def test_job_text_identity_builds_complete_fallback_key(self) -> None:
        identity = JobTextIdentity(
            company="Acme  Brasil",
            title="Pessoa Desenvolvedora Java",
            location="São Paulo, SP",
        )

        self.assertTrue(identity.complete)
        self.assertEqual(
            identity.lookup_key,
            "acme brasil|pessoa desenvolvedora java|sao paulo, sp",
        )

    def test_job_text_identity_marks_missing_parts_as_incomplete(self) -> None:
        identity = JobTextIdentity(company="Acme", title="", location="Remote")

        self.assertFalse(identity.complete)
