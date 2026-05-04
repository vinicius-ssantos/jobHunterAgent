import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from job_hunter_agent.core.source_catalog import (
    CollectionMethod,
    SourceCatalogError,
    SourcePriority,
    SourceRisk,
    find_job_source,
    list_default_job_sources,
    load_job_sources,
    parse_job_sources,
    render_job_sources,
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

    def test_parse_sources_from_json_payload(self) -> None:
        sources = parse_job_sources(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "name": "Custom Board",
                        "method": "api",
                        "priority": "p1",
                        "risk": "low",
                        "notes": "Tested.",
                    }
                ],
            }
        )

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].name, "Custom Board")
        self.assertEqual(sources[0].method, CollectionMethod.API)
        self.assertEqual(sources[0].priority, SourcePriority.P1)

    def test_parse_rejects_duplicate_source_names(self) -> None:
        payload = {
            "sources": [
                {"name": "Dup", "method": "api", "priority": "p1", "risk": "low"},
                {"name": "dup", "method": "api", "priority": "p2", "risk": "low"},
            ]
        }

        with self.assertRaises(SourceCatalogError):
            parse_job_sources(payload)

    def test_load_job_sources_reads_versioned_json_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "source_catalog.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "sources": [
                            {"name": "API Board", "method": "api", "priority": "p1", "risk": "low"}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            sources = load_job_sources(path)

        self.assertEqual(sources[0].name, "API Board")

    def test_render_job_sources_includes_method_risk_priority_and_notes(self) -> None:
        rendered = render_job_sources(parse_job_sources(
            {
                "sources": [
                    {
                        "name": "Visible Board",
                        "method": "scraping",
                        "priority": "p0",
                        "risk": "medium",
                        "has_rate_limit_risk": True,
                        "notes": "Read only.",
                    }
                ]
            }
        ))

        self.assertIn("Fontes de vagas:", rendered)
        self.assertIn("Visible Board: method=scraping; priority=p0; risk=medium", rendered)
        self.assertIn("rate-limit", rendered)
        self.assertIn("Read only.", rendered)
