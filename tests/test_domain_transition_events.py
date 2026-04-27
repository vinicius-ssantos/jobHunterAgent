from __future__ import annotations

from unittest import TestCase

from job_hunter_agent.application.application_commands import (
    ApplicationTransitionCommandService,
    JobReviewCommandService,
)
from job_hunter_agent.application.application_preflight import ApplicationPreflightService
from job_hunter_agent.application.application_submission import ApplicationSubmissionService
from job_hunter_agent.application.contracts import ApplicationFlowInspection, ApplicationSubmissionResult
from job_hunter_agent.core.domain import JobApplication, JobPosting
from job_hunter_agent.core.events import (
    ApplicationAuthorizedV1,
    ApplicationBlockedV1,
    ApplicationPreflightCompletedV1,
    ApplicationSubmittedV1,
    DomainEvent,
    JobReviewedV1,
)


class _EventBus:
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)

    def read_all(self) -> tuple[DomainEvent, ...]:
        return tuple(self.events)


def _job(*, job_id: int = 10, source_site: str = "LinkedIn") -> JobPosting:
    return JobPosting(
        id=job_id,
        title="Backend Java",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url=f"https://www.linkedin.com/jobs/view/{job_id}/",
        source_site=source_site,
        summary="Resumo",
        relevance=9,
        rationale="fit",
        external_key=f"job-key-{job_id}",
        status="collected",
    )


class DomainTransitionEventTests(TestCase):
    def test_review_job_publishes_job_reviewed_when_status_changes(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.marked: list[tuple[int, str, str]] = []

            def get_job(self, job_id: int):
                return _job(job_id=job_id)

            def mark_status(self, job_id: int, status: str, *, detail: str = "") -> None:
                self.marked.append((job_id, status, detail))

        event_bus = _EventBus()
        repository = _Repository()
        service = JobReviewCommandService(repository, event_bus=event_bus)

        detail = service.review_job(10, "approve")

        self.assertEqual(detail, "Vaga aprovada: Backend Java - ACME")
        self.assertEqual(repository.marked, [(10, "approved", "Vaga aprovada: Backend Java - ACME")])
        self.assertEqual(len(event_bus.events), 1)
        event = event_bus.events[0]
        self.assertIsInstance(event, JobReviewedV1)
        self.assertEqual(event.job_id, 10)
        self.assertEqual(event.decision, "approve")
        self.assertEqual(event.status, "approved")
        self.assertEqual(event.reviewed_by, "command")
        self.assertEqual(event.external_key, "job-key-10")
        self.assertEqual(event.correlation_id, "job:10")

    def test_review_job_does_not_publish_when_transition_is_ignored(self) -> None:
        class _Repository:
            def get_job(self, job_id: int):
                return JobPosting(
                    **{**_job(job_id=job_id).__dict__, "status": "approved"}
                )

            def mark_status(self, job_id: int, status: str, *, detail: str = "") -> None:
                raise AssertionError("mark_status should not be called")

        event_bus = _EventBus()
        service = JobReviewCommandService(_Repository(), event_bus=event_bus)

        detail = service.review_job(10, "approve")

        self.assertEqual(detail, "Vaga ja estava aprovada: Backend Java - ACME")
        self.assertEqual(event_bus.events, [])

    def test_authorize_application_publishes_application_authorized(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.marked: list[tuple[int, str, str]] = []

            def get_application(self, application_id: int):
                return JobApplication(id=application_id, job_id=10, status="confirmed")

            def mark_application_status(
                self,
                application_id: int,
                *,
                status: str,
                event_detail="",
                notes=None,
                last_preflight_detail=None,
                last_submit_detail=None,
                last_error=None,
                submitted_at=None,
            ) -> None:
                self.marked.append((application_id, status, event_detail))

        event_bus = _EventBus()
        repository = _Repository()
        service = ApplicationTransitionCommandService(repository, event_bus=event_bus)

        detail = service.authorize_application(55)

        self.assertEqual(detail, "Candidatura autorizada para envio: id=55")
        self.assertEqual(repository.marked, [(55, "authorized_submit", "Candidatura autorizada para envio: id=55")])
        self.assertEqual(len(event_bus.events), 1)
        event = event_bus.events[0]
        self.assertIsInstance(event, ApplicationAuthorizedV1)
        self.assertEqual(event.application_id, 55)
        self.assertEqual(event.job_id, 10)
        self.assertEqual(event.authorized_by, "command")
        self.assertEqual(event.status, "authorized_submit")
        self.assertEqual(event.correlation_id, "application:55")

    def test_application_preflight_publishes_completed_event(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.marked: list[dict[str, object]] = []
                self.events: list[dict[str, object]] = []

            def get_application(self, application_id: int):
                return JobApplication(id=application_id, job_id=10, status="confirmed")

            def get_job(self, job_id: int):
                return _job(job_id=job_id)

            def mark_application_status(self, application_id: int, **kwargs) -> None:
                self.marked.append({"application_id": application_id, **kwargs})

            def record_application_event(self, application_id: int, **kwargs) -> None:
                self.events.append({"application_id": application_id, **kwargs})

        class _Inspector:
            def inspect(self, job: JobPosting):
                return ApplicationFlowInspection(
                    outcome="ready",
                    detail="preflight real ok | pronto_para_envio=sim",
                )

        event_bus = _EventBus()
        service = ApplicationPreflightService(_Repository(), flow_inspector=_Inspector(), event_bus=event_bus)

        result = service.run_for_application(55)

        self.assertEqual(result.outcome, "ready")
        self.assertEqual(result.application_status, "confirmed")
        self.assertEqual(len(event_bus.events), 1)
        event = event_bus.events[0]
        self.assertIsInstance(event, ApplicationPreflightCompletedV1)
        self.assertEqual(event.application_id, 55)
        self.assertEqual(event.job_id, 10)
        self.assertEqual(event.outcome, "ready")
        self.assertEqual(event.application_status, "confirmed")
        self.assertEqual(event.detail, "preflight real ok | pronto_para_envio=sim")
        self.assertEqual(event.correlation_id, "application:55")

    def test_application_preflight_dry_run_does_not_publish_event(self) -> None:
        class _Repository:
            def get_application(self, application_id: int):
                return JobApplication(id=application_id, job_id=10, status="confirmed")

            def get_job(self, job_id: int):
                return _job(job_id=job_id)

        event_bus = _EventBus()
        service = ApplicationPreflightService(_Repository(), event_bus=event_bus)

        result = service.run_dry_run_for_application(55)

        self.assertEqual(result.outcome, "ready")
        self.assertEqual(event_bus.events, [])

    def test_application_submission_publishes_submitted_event(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.marked: list[dict[str, object]] = []
                self.events: list[dict[str, object]] = []

            def get_application(self, application_id: int):
                return JobApplication(
                    id=application_id,
                    job_id=10,
                    status="authorized_submit",
                    last_preflight_detail="preflight real | pronto_para_envio=sim",
                )

            def get_job(self, job_id: int):
                return _job(job_id=job_id)

            def mark_application_status(self, application_id: int, **kwargs) -> None:
                self.marked.append({"application_id": application_id, **kwargs})

            def record_application_event(self, application_id: int, **kwargs) -> None:
                self.events.append({"application_id": application_id, **kwargs})

        class _Applicant:
            def submit(self, application: JobApplication, job: JobPosting):
                return ApplicationSubmissionResult(
                    status="submitted",
                    detail="submissao concluida",
                    submitted_at="2026-04-24T12:00:00+00:00",
                    external_reference="ref-123",
                )

        event_bus = _EventBus()
        repository = _Repository()
        service = ApplicationSubmissionService(repository, applicant=_Applicant(), event_bus=event_bus)

        result = service.run_for_application(55)

        self.assertEqual(result.outcome, "submitted")
        self.assertEqual(result.application_status, "submitted")
        self.assertEqual(len(event_bus.events), 1)
        event = event_bus.events[0]
        self.assertIsInstance(event, ApplicationSubmittedV1)
        self.assertEqual(event.application_id, 55)
        self.assertEqual(event.job_id, 10)
        self.assertEqual(event.portal, "LinkedIn")
        self.assertEqual(event.confirmation_reference, "ref-123")
        self.assertEqual(event.submitted_url, "https://www.linkedin.com/jobs/view/10/")
        self.assertEqual(event.correlation_id, "application:55")

    def test_application_submission_publishes_blocked_event_when_preflight_not_ready(self) -> None:
        class _Repository:
            def __init__(self) -> None:
                self.marked: list[dict[str, object]] = []

            def get_application(self, application_id: int):
                return JobApplication(
                    id=application_id,
                    job_id=10,
                    status="authorized_submit",
                    last_preflight_detail="preflight inconclusivo",
                )

            def get_job(self, job_id: int):
                return _job(job_id=job_id)

            def mark_application_status(self, application_id: int, **kwargs) -> None:
                self.marked.append({"application_id": application_id, **kwargs})

        event_bus = _EventBus()
        service = ApplicationSubmissionService(_Repository(), applicant=object(), event_bus=event_bus)

        result = service.run_for_application(55)

        self.assertEqual(result.outcome, "ignored")
        self.assertEqual(result.application_status, "authorized_submit")
        self.assertEqual(len(event_bus.events), 1)
        event = event_bus.events[0]
        self.assertIsInstance(event, ApplicationBlockedV1)
        self.assertEqual(event.application_id, 55)
        self.assertEqual(event.job_id, 10)
        self.assertEqual(event.reason, "preflight_not_ready")
        self.assertTrue(event.retryable)
        self.assertEqual(event.correlation_id, "application:55")
