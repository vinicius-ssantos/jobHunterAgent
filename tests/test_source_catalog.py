import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from job_hunter_agent.core.source_catalog import (
    CollectionMethod,
    SourceCatalogError,
    SourcePriority,
    find_job_source,
    load_job_sources,
    parse_job_sources,
    render_job_sources,
)


class SourceCatalogTests(TestCase):
    def test_linkedin_is_high_risk_and_not_safe_for_unattended_collection(self) -> None:
        source = find_job_source("linkedin")

        self.assertIsNotNone(source)
        assert source is not None
        self.assertEqual(source.method, CollectionMethod.PLAYWRIGHT)
        self.assertEqual(source.priority, SourcePriority.P0)
        self.assertTrue(source.requires_login)
        self.assertTrue(source.has_captcha_risk)
        self.assertFalse(source.safe_for_unattended_collection)

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
        rendered = render_job_sources(
            parse_job_sources(
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
            )
        )

        self.assertIn("Fontes de vagas:", rendered)
        self.assertIn("Visible Board: method=scraping; priority=p0; risk=medium", rendered)
        self.assertIn("rate-limit", rendered)
        self.assertIn("Read only.", rendered)
