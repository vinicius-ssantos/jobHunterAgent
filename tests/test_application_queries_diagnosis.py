from unittest import TestCase

from job_hunter_agent.application.application_queries import ApplicationQueryService
from job_hunter_agent.core.domain import JobApplication, JobApplicationEvent, JobPosting
from job_hunter_agent.core.events import ApplicationBlockedV1, ApplicationSubmittedV1


class _RepositoryStub:
    def __init__(self) -> None:
        self.application = JobApplication(
            id=32,
            job_id=10,
            status="error_submit",
            support_level="manual_review",
            last_error="readiness=listing_redirect",
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
            external_key="linkedin-10",
            status="approved",
        )
        self.events = [
            JobApplicationEvent(
                id=1,
                application_id=32,
                event_type="submit_error",
                from_status="authorized_submit",
                to_status="error_submit",
                detail="submit falhou",
                created_at="2026-04-27T10:00:00",
            )
        ]

    def get_application(self, application_id: int) -> JobApplication | None:
        if application_id == 32:
            return self.application
        return None

    def get_job(self, job_id: int) -> JobPosting | None:
        if job_id == 10:
            return self.job
        return None

    def list_application_events(self, application_id: int, *, limit: int) -> list[JobApplicationEvent]:
        assert application_id == 32
        assert limit == 10
        return self.events


class _DomainEventBusStub:
    def read_all(self) -> tuple[object, ...]:
        return (
            ApplicationSubmittedV1(
                application_id=99,
                job_id=99,
                portal="LinkedIn",
                occurred_at="2026-04-27T09:00:00+00:00",
                correlation_id="application:99",
            ),
            ApplicationBlockedV1(
                application_id=32,
                job_id=10,
                reason="listing_redirect",
                detail="navegacao caiu em listagem",
                retryable=True,
                occurred_at="2026-04-27T10:01:00+00:00",
                correlation_id="application:32",
            ),
        )


class ApplicationQueryServiceDiagnosisTests(TestCase):
    def test_diagnose_application_aggregates_repository_and_matching_domain_events(self) -> None:
        service = ApplicationQueryService(
            repository=_RepositoryStub(),
            domain_event_bus=_DomainEventBusStub(),
        )

        rendered = service.diagnose_application(32)

        self.assertIn("Diagnostico da candidatura 32", rendered)
        self.assertIn("titulo=Backend Java", rendered)
        self.assertIn("submit_error", rendered)
        self.assertIn("ApplicationBlockedV1", rendered)
        self.assertIn("correlation_id=application:32", rendered)
        self.assertNotIn("application:99", rendered)

    def test_diagnose_application_reports_missing_application(self) -> None:
        service = ApplicationQueryService(repository=_RepositoryStub())

        rendered = service.diagnose_application(404)

        self.assertEqual("Candidatura nao encontrada: id=404", rendered)
