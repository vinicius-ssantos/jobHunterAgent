from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from job_hunter_agent.api.dependencies import get_repository
from job_hunter_agent.api.schemas import (
    JobDetailResponse,
    JobResponse,
    application_to_response,
    job_event_to_response,
    job_to_response,
)
from job_hunter_agent.core.domain import VALID_STATUSES
from job_hunter_agent.infrastructure.repository import JobRepository

router = APIRouter(prefix="/jobs", tags=["jobs"])

JOB_STATUS_ORDER = ("collected", "approved", "rejected", "error_collect")


@router.get("", response_model=list[JobResponse])
def list_jobs(
    status: str | None = Query(default=None),
    repository: JobRepository = Depends(get_repository),
) -> list[JobResponse]:
    statuses = _resolve_job_statuses(status)
    jobs: list[object] = []
    for current_status in statuses:
        jobs.extend(repository.list_jobs_by_status(current_status))
    return [job_to_response(job) for job in jobs]


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: int, repository: JobRepository = Depends(get_repository)) -> JobDetailResponse:
    job = repository.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Vaga nao encontrada: id={job_id}")
    application = repository.get_application_by_job(job_id)
    events = repository.list_job_events(job_id, limit=20)
    base = job_to_response(job)
    return JobDetailResponse(
        **base.model_dump(),
        application=application_to_response(application) if application is not None else None,
        events=[job_event_to_response(event) for event in events],
    )


def _resolve_job_statuses(status: str | None) -> tuple[str, ...]:
    if status is None or status == "all":
        return tuple(current for current in JOB_STATUS_ORDER if current in VALID_STATUSES)
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status de vaga invalido: {status}")
    return (status,)
