from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from job_hunter_agent.api.dependencies import get_repository
from job_hunter_agent.api.schemas import (
    ApplicationDetailResponse,
    ApplicationEventResponse,
    ApplicationResponse,
    application_event_to_response,
    application_to_response,
)
from job_hunter_agent.core.domain import VALID_APPLICATION_STATUSES
from job_hunter_agent.infrastructure.repository import JobRepository

router = APIRouter(prefix="/applications", tags=["applications"])

APPLICATION_STATUS_ORDER = (
    "draft",
    "ready_for_review",
    "confirmed",
    "authorized_submit",
    "submitted",
    "error_submit",
    "cancelled",
)


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    status: str | None = Query(default=None),
    repository: JobRepository = Depends(get_repository),
) -> list[ApplicationResponse]:
    statuses = _resolve_application_statuses(status)
    applications: list[ApplicationResponse] = []
    for current_status in statuses:
        list_with_jobs = getattr(repository, "list_applications_with_jobs_by_status", None)
        if list_with_jobs is None:
            for application in repository.list_applications_by_status(current_status):
                applications.append(application_to_response(application, repository.get_job(application.job_id)))
            continue
        applications.extend(
            application_to_response(application, job)
            for application, job in list_with_jobs(current_status)
        )
    return applications


@router.get("/{application_id}", response_model=ApplicationDetailResponse)
def get_application(
    application_id: int,
    repository: JobRepository = Depends(get_repository),
) -> ApplicationDetailResponse:
    application = repository.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail=f"Candidatura nao encontrada: id={application_id}")
    job = repository.get_job(application.job_id)
    events = repository.list_application_events(application_id, limit=20)
    base = application_to_response(application, job)
    return ApplicationDetailResponse(
        **base.model_dump(),
        events=[application_event_to_response(event) for event in events],
    )


@router.get("/{application_id}/events", response_model=list[ApplicationEventResponse])
def list_application_events(
    application_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    repository: JobRepository = Depends(get_repository),
) -> list[ApplicationEventResponse]:
    application = repository.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail=f"Candidatura nao encontrada: id={application_id}")
    events = repository.list_application_events(application_id, limit=limit)
    return [application_event_to_response(event) for event in events]


def _resolve_application_statuses(status: str | None) -> tuple[str, ...]:
    if status is None or status == "all":
        return tuple(current for current in APPLICATION_STATUS_ORDER if current in VALID_APPLICATION_STATUSES)
    if status not in VALID_APPLICATION_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status de candidatura invalido: {status}")
    return (status,)
