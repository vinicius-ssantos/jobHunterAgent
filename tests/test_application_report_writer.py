import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from job_hunter_agent.application.application_report import (
    ApplicationReportAlreadyExistsError,
    build_application_report_manifest_path,
    build_application_report_manifest_path_for_report,
    build_application_report_path,
    write_application_report,
)
from job_hunter_agent.core.domain import JobApplication, JobPosting


def _application() -> JobApplication:
    return JobApplication(
        id=32,
        job_id=10,
        status="confirmed",
        support_level="manual_review",
        support_rationale="portal exige revisao",
    )


def _job() -> JobPosting:
    return JobPosting(
        id=10,
        title="Backend Java",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url="https://example.com/job",
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia",
        external_key="job-10",
        status="approved",
    )


class ApplicationReportWriterTests(TestCase):
    def test_build_application_report_paths_use_deterministic_names(self) -> None:
        self.assertEqual(
            str(build_application_report_path(32)),
            "artifacts/reports/application-32.md",
        )
        self.assertEqual(
            str(build_application_report_manifest_path(32)),
            "artifacts/reports/application-32.json",
        )
        self.assertEqual(
            build_application_report_manifest_path_for_report(Path("custom/report.md")),
            Path("custom/report.json"),
        )

    def test_write_application_report_writes_markdown_and_manifest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir) / "reports"

            artifacts = write_application_report(
                application=_application(),
                job=_job(),
                events=[],
                reports_dir=reports_dir,
            )

            self.assertEqual(artifacts.report_path, reports_dir / "application-32.md")
            self.assertEqual(artifacts.manifest_path, reports_dir / "application-32.json")
            self.assertIn("# Relatorio Da Candidatura 32", artifacts.report_path.read_text(encoding="utf-8"))
            manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["application"]["id"], 32)
            self.assertEqual(manifest["application"]["status"], "confirmed")
            self.assertEqual(manifest["job"]["id"], 10)
            self.assertEqual(manifest["job"]["company"], "ACME")
            self.assertEqual(manifest["status"]["application"], "confirmed")
            self.assertEqual(manifest["support"]["level"], "manual_review")
            self.assertEqual(manifest["report_path"], str(artifacts.report_path))
            self.assertEqual(manifest["manifest_path"], str(artifacts.manifest_path))
            self.assertTrue(manifest["safety"]["read_only"])
            self.assertFalse(manifest["safety"]["uses_llm"])
            self.assertFalse(manifest["safety"]["runs_preflight"])
            self.assertFalse(manifest["safety"]["runs_submit"])
            self.assertFalse(manifest["safety"]["changes_status"])
            self.assertIn("generated_at_utc", manifest)

    def test_write_application_report_uses_custom_manifest_path_from_output(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "custom.md"

            artifacts = write_application_report(
                application=_application(),
                job=_job(),
                events=[],
                output_path=output,
            )

            self.assertEqual(artifacts.report_path, output)
            self.assertEqual(artifacts.manifest_path, Path(temp_dir) / "nested" / "custom.json")
            self.assertTrue(artifacts.report_path.exists())
            self.assertTrue(artifacts.manifest_path.exists())

    def test_write_application_report_blocks_existing_markdown_without_force(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.md"
            manifest = Path(temp_dir) / "report.json"
            output.write_text("existing", encoding="utf-8")

            with self.assertRaises(ApplicationReportAlreadyExistsError) as raised:
                write_application_report(
                    application=_application(),
                    job=_job(),
                    events=[],
                    output_path=output,
                )

            self.assertEqual(raised.exception.path, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")
            self.assertFalse(manifest.exists())

    def test_write_application_report_blocks_existing_manifest_without_force(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.md"
            manifest = Path(temp_dir) / "report.json"
            manifest.write_text("existing", encoding="utf-8")

            with self.assertRaises(ApplicationReportAlreadyExistsError) as raised:
                write_application_report(
                    application=_application(),
                    job=_job(),
                    events=[],
                    output_path=output,
                )

            self.assertEqual(raised.exception.path, manifest)
            self.assertFalse(output.exists())
            self.assertEqual(manifest.read_text(encoding="utf-8"), "existing")

    def test_write_application_report_overwrites_existing_files_with_force(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.md"
            manifest = Path(temp_dir) / "report.json"
            output.write_text("existing", encoding="utf-8")
            manifest.write_text("existing", encoding="utf-8")

            artifacts = write_application_report(
                application=_application(),
                job=_job(),
                events=[],
                output_path=output,
                force=True,
            )

            self.assertEqual(artifacts.report_path, output)
            self.assertEqual(artifacts.manifest_path, manifest)
            self.assertIn("# Relatorio Da Candidatura 32", output.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["application"]["id"], 32)
