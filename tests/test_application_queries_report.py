from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from job_hunter_agent.application.application_report import (
    ApplicationReportAlreadyExistsError,
    ApplicationReportArtifacts,
)
from job_hunter_agent.application.application_queries import ApplicationQueryService
from job_hunter_agent.core.domain import JobApplication, JobApplicationEvent, JobPosting


class _RepositoryStub:
    def __init__(self) -> None:
        self.application = JobApplication(
            id=32,
            job_id=10,
            status="confirmed",
            support_level="manual_review",
        )
        self.job = JobPosting(
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
        self.events = [
            JobApplicationEvent(
                id=1,
                application_id=32,
                event_type="status_changed",
                from_status="ready_for_review",
                to_status="confirmed",
                detail="confirmada por humano",
                created_at="2026-04-29T10:00:00",
            )
        ]

    def get_application(self, application_id: int) -> JobApplication | None:
        if application_id == 32:
            return self.application
        if application_id == 33:
            return JobApplication(id=33, job_id=404, status="draft")
        return None

    def get_job(self, job_id: int) -> JobPosting | None:
        if job_id == 10:
            return self.job
        return None

    def list_application_events(self, application_id: int, *, limit: int) -> list[JobApplicationEvent]:
        assert application_id == 32
        assert limit == 10
        return self.events


class ApplicationQueryServiceReportTests(TestCase):
    def test_generate_application_report_writes_markdown_and_manifest_and_returns_paths(self) -> None:
        service = ApplicationQueryService(repository=_RepositoryStub())

        with patch(
            "job_hunter_agent.application.application_queries.write_application_report",
            return_value=ApplicationReportArtifacts(
                report_path=Path("artifacts/reports/application-32.md"),
                manifest_path=Path("artifacts/reports/application-32.json"),
            ),
        ) as write_report:
            rendered = service.generate_application_report(32)

        self.assertEqual(
            rendered,
            "Relatorio gerado: artifacts/reports/application-32.md\n"
            "Manifesto gerado: artifacts/reports/application-32.json",
        )
        write_report.assert_called_once()
        kwargs = write_report.call_args.kwargs
        self.assertEqual(kwargs["application"].id, 32)
        self.assertEqual(kwargs["job"].id, 10)
        self.assertEqual(len(kwargs["events"]), 1)
        self.assertIsNone(kwargs["output_path"])
        self.assertFalse(kwargs["force"])

    def test_generate_application_report_passes_output_path_and_force(self) -> None:
        service = ApplicationQueryService(repository=_RepositoryStub())
        output_path = Path("custom/report.md")

        with patch(
            "job_hunter_agent.application.application_queries.write_application_report",
            return_value=ApplicationReportArtifacts(
                report_path=output_path,
                manifest_path=Path("custom/report.json"),
            ),
        ) as write_report:
            rendered = service.generate_application_report(32, output_path=output_path, force=True)

        self.assertEqual(rendered, "Relatorio gerado: custom/report.md\nManifesto gerado: custom/report.json")
        kwargs = write_report.call_args.kwargs
        self.assertEqual(kwargs["output_path"], output_path)
        self.assertTrue(kwargs["force"])

    def test_generate_application_report_reports_existing_file_without_force(self) -> None:
        service = ApplicationQueryService(repository=_RepositoryStub())

        with patch(
            "job_hunter_agent.application.application_queries.write_application_report",
            side_effect=ApplicationReportAlreadyExistsError(Path("custom/report.json")),
        ):
            rendered = service.generate_application_report(32)

        self.assertEqual(rendered, "Relatorio ja existe: custom/report.json. Use --force para sobrescrever.")

    def test_generate_application_report_reports_missing_application(self) -> None:
        service = ApplicationQueryService(repository=_RepositoryStub())

        rendered = service.generate_application_report(404)

        self.assertEqual(rendered, "Candidatura nao encontrada: id=404")

    def test_generate_application_report_reports_missing_job(self) -> None:
        service = ApplicationQueryService(repository=_RepositoryStub())

        rendered = service.generate_application_report(33)

        self.assertEqual(rendered, "Vaga associada nao encontrada: application_id=33 job_id=404")
