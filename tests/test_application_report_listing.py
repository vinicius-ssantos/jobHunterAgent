import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from job_hunter_agent.application.application_report_listing import (
    list_application_reports,
    render_application_reports_list,
)


class ApplicationReportListingTests(TestCase):
    def test_list_application_reports_uses_manifest_when_available(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            report = reports_dir / "application-32.md"
            manifest = reports_dir / "application-32.json"
            report.write_text("# Relatorio", encoding="utf-8")
            manifest.write_text(
                json.dumps(
                    {
                        "application": {"id": 32, "job_id": 10, "status": "confirmed"},
                        "generated_at_utc": "2026-04-30T10:00:00+00:00",
                        "job": {
                            "id": 10,
                            "title": "Backend Java",
                            "company": "ACME",
                            "status": "approved",
                        },
                        "status": {"application": "confirmed", "job": "approved"},
                        "support": {"level": "manual_review"},
                    }
                ),
                encoding="utf-8",
            )

            items = list_application_reports(reports_dir=reports_dir)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].application_id, 32)
        self.assertEqual(items[0].job_id, 10)
        self.assertEqual(items[0].application_status, "confirmed")
        self.assertEqual(items[0].job_status, "approved")
        self.assertEqual(items[0].company, "ACME")
        self.assertEqual(items[0].title, "Backend Java")
        self.assertEqual(items[0].generated_at_utc, "2026-04-30T10:00:00+00:00")
        self.assertEqual(items[0].manifest_status, "ok")

    def test_list_application_reports_falls_back_to_markdown_without_manifest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            (reports_dir / "application-45.md").write_text("# Relatorio", encoding="utf-8")

            items = list_application_reports(reports_dir=reports_dir)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].application_id, 45)
        self.assertIsNone(items[0].job_id)
        self.assertEqual(items[0].manifest_status, "missing")

    def test_list_application_reports_keeps_invalid_manifest_item(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            (reports_dir / "application-46.md").write_text("# Relatorio", encoding="utf-8")
            (reports_dir / "application-46.json").write_text("{invalid", encoding="utf-8")

            items = list_application_reports(reports_dir=reports_dir)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].application_id, 46)
        self.assertEqual(items[0].manifest_status, "invalid")

    def test_list_application_reports_orders_by_modified_time_and_applies_limit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            first = reports_dir / "application-1.md"
            second = reports_dir / "application-2.md"
            first.write_text("# 1", encoding="utf-8")
            second.write_text("# 2", encoding="utf-8")
            first.touch()
            second.touch()

            items = list_application_reports(reports_dir=reports_dir, limit=1)

        self.assertEqual(len(items), 1)
        self.assertIn(items[0].application_id, {1, 2})

    def test_list_application_reports_returns_empty_for_missing_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"

            items = list_application_reports(reports_dir=missing)

        self.assertEqual(items, [])

    def test_list_application_reports_rejects_non_positive_limit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                list_application_reports(reports_dir=Path(temp_dir), limit=0)

    def test_render_application_reports_list(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            (reports_dir / "application-45.md").write_text("# Relatorio", encoding="utf-8")

            rendered = render_application_reports_list(reports_dir=reports_dir)

        self.assertIn(f"Relatorios A-F em {reports_dir}", rendered)
        self.assertIn("application_id=45", rendered)
        self.assertIn("manifesto=missing", rendered)
        self.assertIn("markdown=", rendered)

    def test_render_application_reports_list_handles_empty_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)

            rendered = render_application_reports_list(reports_dir=reports_dir)

        self.assertEqual(rendered, f"Nenhum relatorio encontrado em {reports_dir}")
