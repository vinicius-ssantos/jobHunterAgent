from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from job_hunter_agent.application.application_report import (
    ApplicationReportAlreadyExistsError,
    build_application_report_path,
    write_application_report,
)
from job_hunter_agent.core.domain import JobApplication, JobPosting


def _application() -> JobApplication:
    return JobApplication(id=32, job_id=10, status="confirmed", support_level="manual_review")


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
    def test_build_application_report_path_uses_deterministic_name(self) -> None:
        self.assertEqual(
            str(build_application_report_path(32)),
            "artifacts/reports/application-32.md",
        )

    def test_write_application_report_blocks_existing_file_without_force(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.md"
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

    def test_write_application_report_overwrites_existing_file_with_force(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.md"
            output.write_text("existing", encoding="utf-8")

            written = write_application_report(
                application=_application(),
                job=_job(),
                events=[],
                output_path=output,
                force=True,
            )

            self.assertEqual(written, output)
            self.assertIn("# Relatorio Da Candidatura 32", output.read_text(encoding="utf-8"))

    def test_write_application_report_creates_custom_parent_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "custom.md"

            written = write_application_report(
                application=_application(),
                job=_job(),
                events=[],
                output_path=output,
            )

            self.assertEqual(written, output)
            self.assertTrue(output.exists())
