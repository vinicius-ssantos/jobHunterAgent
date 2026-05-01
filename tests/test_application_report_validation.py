import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from job_hunter_agent.application.application_report_validation import (
    render_application_reports_validation,
    validate_application_reports,
)


def _valid_manifest(report_path: Path, manifest_path: Path) -> dict[str, object]:
    return {
        "application": {"id": 32, "job_id": 10, "status": "confirmed"},
        "generated_at_utc": "2026-04-30T10:00:00+00:00",
        "job": {"id": 10, "title": "Backend Java", "company": "ACME", "status": "approved"},
        "manifest_path": str(manifest_path),
        "report_path": str(report_path),
        "safety": {
            "changes_status": False,
            "read_only": True,
            "runs_preflight": False,
            "runs_submit": False,
            "uses_llm": False,
        },
        "status": {"application": "confirmed", "job": "approved"},
        "support": {"level": "manual_review", "rationale": "portal exige revisao"},
    }


class ApplicationReportValidationTests(TestCase):
    def test_validate_application_reports_accepts_valid_pair(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            report = reports_dir / "application-32.md"
            manifest = reports_dir / "application-32.json"
            report.write_text("# Relatorio", encoding="utf-8")
            manifest.write_text(json.dumps(_valid_manifest(report, manifest)), encoding="utf-8")

            result = validate_application_reports(reports_dir=reports_dir)

        self.assertEqual(result.ok_count, 1)
        self.assertEqual(result.warning_count, 0)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.issues, ())

    def test_validate_application_reports_warns_for_markdown_without_manifest_by_default(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            (reports_dir / "application-32.md").write_text("# Relatorio", encoding="utf-8")

            result = validate_application_reports(reports_dir=reports_dir)

        self.assertEqual(result.ok_count, 0)
        self.assertEqual(result.warning_count, 1)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.issues[0].message, "Markdown sem manifesto JSON correspondente")

    def test_validate_application_reports_errors_for_markdown_without_manifest_in_strict_mode(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            (reports_dir / "application-32.md").write_text("# Relatorio", encoding="utf-8")

            result = validate_application_reports(reports_dir=reports_dir, strict=True)

        self.assertEqual(result.ok_count, 0)
        self.assertEqual(result.warning_count, 0)
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.issues[0].level, "error")

    def test_validate_application_reports_warns_for_manifest_without_markdown_by_default(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            manifest = reports_dir / "application-32.json"
            manifest.write_text("{}", encoding="utf-8")

            result = validate_application_reports(reports_dir=reports_dir)

        self.assertEqual(result.warning_count, 1)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.issues[0].message, "manifesto JSON sem Markdown correspondente")

    def test_validate_application_reports_reports_invalid_json(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            (reports_dir / "application-32.md").write_text("# Relatorio", encoding="utf-8")
            (reports_dir / "application-32.json").write_text("{invalid", encoding="utf-8")

            result = validate_application_reports(reports_dir=reports_dir)

        self.assertEqual(result.ok_count, 0)
        self.assertEqual(result.error_count, 1)
        self.assertIn("manifesto JSON invalido", result.issues[0].message)

    def test_validate_application_reports_reports_missing_required_field(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            report = reports_dir / "application-32.md"
            manifest = reports_dir / "application-32.json"
            report.write_text("# Relatorio", encoding="utf-8")
            data = _valid_manifest(report, manifest)
            del data["support"]
            manifest.write_text(json.dumps(data), encoding="utf-8")

            result = validate_application_reports(reports_dir=reports_dir)

        self.assertEqual(result.ok_count, 0)
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.issues[0].message, "campo obrigatorio ausente: support")

    def test_validate_application_reports_reports_wrong_safety_flag(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            report = reports_dir / "application-32.md"
            manifest = reports_dir / "application-32.json"
            report.write_text("# Relatorio", encoding="utf-8")
            data = _valid_manifest(report, manifest)
            data["safety"]["uses_llm"] = True  # type: ignore[index]
            manifest.write_text(json.dumps(data), encoding="utf-8")

            result = validate_application_reports(reports_dir=reports_dir)

        self.assertEqual(result.ok_count, 0)
        self.assertEqual(result.error_count, 1)
        self.assertIn("flag de safety invalida: uses_llm=True", result.issues[0].message)

    def test_validate_application_reports_reports_path_mismatch(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            report = reports_dir / "application-32.md"
            manifest = reports_dir / "application-32.json"
            report.write_text("# Relatorio", encoding="utf-8")
            data = _valid_manifest(report, manifest)
            data["report_path"] = "other.md"
            manifest.write_text(json.dumps(data), encoding="utf-8")

            result = validate_application_reports(reports_dir=reports_dir)

        self.assertEqual(result.ok_count, 0)
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.issues[0].message, "report_path nao aponta para o Markdown validado")

    def test_render_application_reports_validation_includes_summary_and_issues(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            (reports_dir / "application-32.md").write_text("# Relatorio", encoding="utf-8")

            rendered = render_application_reports_validation(reports_dir=reports_dir, strict=True)

        self.assertIn(f"Validacao de relatorios A-F em {reports_dir}", rendered)
        self.assertIn("- ok=0", rendered)
        self.assertIn("- warnings=0", rendered)
        self.assertIn("- errors=1", rendered)
        self.assertIn("- strict=true", rendered)
        self.assertIn("Markdown sem manifesto JSON correspondente", rendered)

    def test_validate_application_reports_warns_for_missing_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir) / "missing"

            result = validate_application_reports(reports_dir=reports_dir)

        self.assertEqual(result.ok_count, 0)
        self.assertEqual(result.warning_count, 1)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.issues[0].message, "diretorio de relatorios nao existe")
