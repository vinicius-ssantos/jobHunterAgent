from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from job_hunter_agent.core.domain import JobApplication, JobPosting
from job_hunter_agent.infrastructure.repository import JobRepository


@dataclass(frozen=True)
class ApplicationExecutionContext:
    application: JobApplication
    job: JobPosting


def load_application_context(repository: JobRepository, application_id: int) -> ApplicationExecutionContext:
    application = repository.get_application(application_id)
    if not application:
        raise ValueError(f"Application not found: {application_id}")
    job = repository.get_job(application.job_id)
    if not job:
        raise ValueError(f"Job not found for application: {application_id}")
    return ApplicationExecutionContext(application=application, job=job)


class ApplicationFlowCoordinator:
    def __init__(self, repository: JobRepository) -> None:
        self.repository = repository

    def record_preflight_result(
        self,
        context: ApplicationExecutionContext,
        *,
        outcome: str,
        detail: str,
        event_type: str,
        status: str,
        clear_error: bool,
    ) -> str:
        self.repository.mark_application_status(
            context.application.id,
            status=status,
            last_preflight_detail=detail,
            last_error="" if clear_error else detail,
        )
        self.record_event(
            context.application.id,
            event_type=event_type,
            detail=detail,
            from_status=context.application.status,
            to_status=status,
        )
        return status

    def record_submit_result(
        self,
        context: ApplicationExecutionContext,
        *,
        detail: str,
        event_type: str,
        status: str,
        clear_error: bool,
        submitted_at: str | None = None,
    ) -> str:
        self.repository.mark_application_status(
            context.application.id,
            status=status,
            last_submit_detail=detail,
            last_error="" if clear_error else detail,
            submitted_at=submitted_at,
        )
        self.record_event(
            context.application.id,
            event_type=event_type,
            detail=detail,
            from_status=context.application.status,
            to_status=status,
        )
        return status

    def record_event(
        self,
        application_id: int,
        *,
        event_type: str,
        detail: str = "",
        from_status: str | None = None,
        to_status: str | None = None,
    ) -> None:
        self.repository.record_application_event(
            application_id,
            event_type=event_type,
            detail=detail,
            from_status=from_status,
            to_status=to_status,
        )

    @staticmethod
    def resolve_submitted_at(submitted_at: str | None) -> str:
        return submitted_at or datetime.now().isoformat(timespec="seconds")
