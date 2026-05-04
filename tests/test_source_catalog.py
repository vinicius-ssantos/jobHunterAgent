from unittest import TestCase

from job_hunter_agent.core.source_catalog import (
    CollectionMethod,
    SourcePriority,
    SourceRisk,
    find_job_source,
    list_default_job_sources,
    safe_unattended_sources,
    sources_by_priority,
)


class SourceCatalogTests(TestCase):
    def test_default_sources_include_core_pipeline_targets(self) -> None:
        names = {source.name for source in list_default_job_sources()}

        self.assertIn("LinkedIn", names)
        self.assertIn("Gupy", names)
        self.assertIn("Greenhouse", names)
        self.assertIn("Lever", names)

    def test_linkedin_is_high_risk_and_not_safe_for_unattended_collection(self) -> None:
        source = find_job_source("linkedin")

        self.assertIsNotNone(source)
        assert source is not None
        self.assertEqual(source.method, CollectionMethod.PLAYWRIGHT)
        self.assertEqual(source.priority, SourcePriority.P0)
        self.assertEqual(source.risk, SourceRisk.HIGH)
        self.assertTrue(source.requires_login)
        self.assertTrue(source.has_captcha_risk)
        self.assertFalse(source.safe_for_unattended_collection)

    def test_public_api_sources_are_safe_for_unattended_collection(self) -> None:
        safe_names = {source.name for source in safe_unattended_sources()}

        self.assertIn("Greenhouse", safe_names)
        self.assertIn("Lever", safe_names)
        self.assertNotIn("LinkedIn", safe_names)

    def test_sources_can_be_filtered_by_priority(self) -> None:
        p0_names = {source.name for source in sources_by_priority(SourcePriority.P0)}

        self.assertEqual(p0_names, {"LinkedIn", "Gupy"})

    def test_unknown_source_returns_none(self) -> None:
        self.assertIsNone(find_job_source("unknown board"))
