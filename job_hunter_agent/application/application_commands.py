from __future__ import annotations

from job_hunter_agent.application.application_messages import (
    format_created_application_draft,
    format_existing_application_for_job,
    format_job_not_approved_for_draft,
)
from job_hunter_agent.application.contracts import PreparationPort
from job_hunter_agent.application.review_workflow import resolve_application_action, resolve_review_action
from job_hunter_agent.core.event_bus import EventBusPort
from job_hunter_agent.core.events import ApplicationAuthorizedV1, ApplicationDraftCreatedV1, JobReviewedV1
from job_hunter_agent.infrastructure.repository import JobRepository


class JobReviewCommandService:
    def __init__(self, repository: JobRepository, event_bus: EventBusPort | None = None) -> None:
        self.repository = repository
        self.event_bus = event_bus

    def review_job(self, job_id: int, action: str) -> str:
        job = self.repository.get_job(job_id)
        if job is None:
            return f"Vaga nao encontrada: id={job_id}"
        next_status, detail = resolve_review_action(job, action)
        if next_status is None:
            return detail
        self.repository.mark_status(job_id, next_status, detail=detail)
        if self.event_bus is not None:
            self.event_bus.publish(
                JobReviewedV1(
                    job_id=job_id,
                    decision=action,
                    status=next_status,
                    reviewed_by="command",
                    notes=detail,
                    external_key=job.external_key,
                    correlation_id=f"job:{job_id}",
                )
            )
        return detail


class ApplicationDraftCommandService:
    def __init__(
        self,
        repository: JobRepository,
        preparation_service: PreparationPort,
        event_bus: EventBusPort | None = None,
    ) -> None:
        self.repository = repository
        self.preparation_service = preparation_service
        self.event_bus = event_bus

    def create_application_draft_for_job(self, job_id: int) -> str:
        job = self.repository.get_job(job_id)
        if job is None:
            return f"Vaga nao encontrada: id={job_id}"
        existing = self.repository.get_application_by_job(job_id)
        if existing is not None:
            return format_existing_application_for_job(
                application=existing,
                job_id=job_id,
            )
        drafts = self.preparation_service.create_drafts_for_approved_jobs(
            [job_id],
            notes="rascunho criado via cli apos aprovacao humana",
        )
        if not drafts:
            return format_job_not_approved_for_draft(job_id=job_id)
        draft = drafts[0]
        if self.event_bus is not None:
            self.event_bus.publish(
                ApplicationDraftCreatedV1(
                    application_id=draft.id or 0,
                    job_id=job_id,
                    status=draft.status,
                    support_level=draft.support_level,
                    created_by="command",
                    correlation_id=f"application:{draft.id}" if draft.id is not None else f"job:{job_id}",
                )
            )
        return format_created_application_draft(
            application_id=draft.id,
            job_id=job_id,
            status=draft.status,
            support_level=draft.support_level,
        )


class ApplicationTransitionCommandService:
    def __init__(self, repository: JobRepository, event_bus: EventBusPort | None = None) -> None:
        self.repository = repository
        self.event_bus = event_bus

    def transition_application(self, application_id: int, action: str) -> str:
        application = self.repository.get_application(application_id)
        if application is None:
            return f"Candidatura nao encontrada: id={application_id}"
        next_status, detail = resolve_application_action(application, action)
        if next_status is None:
            return detail
        self.repository.mark_application_status(application_id, status=next_status, event_detail=detail)
        if self.event_bus is not None and next_status == "authorized_submit":
            self.event_bus.publish(
                ApplicationAuthorizedV1(
                    application_id=application_id,
                    job_id=application.job_id,
                    authorized_by="command",
                    authorization_source="manual",
                    status=next_status,
                    correlation_id=f"application:{application_id}",
                )
            )
        return detail

    def authorize_application(self, application_id: int) -> str:
        return self.transition_application(application_id, "app_authorize")
