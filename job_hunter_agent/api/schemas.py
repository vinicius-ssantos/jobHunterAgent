from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ApiError(BaseModel):
    detail: str


class ActionResponse(BaseModel):
    detail: str
    job: Optional[JobResponse] = None
    application: Optional[ApplicationResponse] = None


class JobEventResponse(BaseModel):
    id: Optional[int] = None
    job_id: int
    event_type: str
    detail: str = ""
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    created_at: Optional[str] = None


class JobResponse(BaseModel):
    id: Optional[int] = None
    title: str
    company: str
    location: str
    work_mode: str
    salary_text: str
    url: str
    source_site: str
    summary: str
    relevance: int
    rationale: str
    external_key: str
    status: str
    created_at: Optional[str] = None


class ApplicationEventResponse(BaseModel):
    id: Optional[int] = None
    application_id: int
    event_type: str
    detail: str = ""
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    created_at: Optional[str] = None


class ApplicationResponse(BaseModel):
    id: Optional[int] = None
    job_id: int
    status: str
    support_level: str
    support_rationale: str = ""
    notes: str = ""
    last_preflight_detail: str = ""
    last_submit_detail: str = ""
    last_error: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    submitted_at: Optional[str] = None
    job: Optional[JobResponse] = None


class JobDetailResponse(JobResponse):
    application: Optional[ApplicationResponse] = None
    events: list[JobEventResponse] = []


class ApplicationDetailResponse(ApplicationResponse):
    events: list[ApplicationEventResponse] = []


class StatusOverviewResponse(BaseModel):
    jobs: dict[str, int]
    applications: dict[str, int]


class HealthCheckItemResponse(BaseModel):
    name: str
    status: str
    detail: str


class HealthReportResponse(BaseModel):
    ok: bool
    items: list[HealthCheckItemResponse]


class OperationNextActionResponse(BaseModel):
    priority: int
    application_id: int
    job_id: int
    status: str
    title: str
    company: str
    reason_code: str
    command: str
    note: str


class CollectionRunSummaryResponse(BaseModel):
    total_runs: int = 0
    success_runs: int = 0
    error_runs: int = 0
    interrupted_runs: int = 0
    running_runs: int = 0
    jobs_seen: int = 0
    jobs_saved: int = 0
    errors: int = 0


class CollectionLogSummaryResponse(BaseModel):
    by_source: dict[str, int]
    by_level: dict[str, int]
    recent_warnings_or_errors: list[dict[str, str]]


class CollectionOperationsReportResponse(BaseModel):
    run_summary: CollectionRunSummaryResponse
    log_summary: CollectionLogSummaryResponse


class OperationsReportResponse(BaseModel):
    collection: CollectionOperationsReportResponse


def job_to_response(job: object) -> JobResponse:
    return JobResponse(
        id=getattr(job, "id", None),
        title=str(getattr(job, "title", "")),
        company=str(getattr(job, "company", "")),
        location=str(getattr(job, "location", "")),
        work_mode=str(getattr(job, "work_mode", "")),
        salary_text=str(getattr(job, "salary_text", "")),
        url=str(getattr(job, "url", "")),
        source_site=str(getattr(job, "source_site", "")),
        summary=str(getattr(job, "summary", "")),
        relevance=int(getattr(job, "relevance", 0)),
        rationale=str(getattr(job, "rationale", "")),
        external_key=str(getattr(job, "external_key", "")),
        status=str(getattr(job, "status", "")),
        created_at=getattr(job, "created_at", None),
    )


def job_event_to_response(event: object) -> JobEventResponse:
    return JobEventResponse(
        id=getattr(event, "id", None),
        job_id=int(getattr(event, "job_id")),
        event_type=str(getattr(event, "event_type", "")),
        detail=str(getattr(event, "detail", "")),
        from_status=getattr(event, "from_status", None),
        to_status=getattr(event, "to_status", None),
        created_at=getattr(event, "created_at", None),
    )


def application_to_response(application: object, job: object | None = None) -> ApplicationResponse:
    return ApplicationResponse(
        id=getattr(application, "id", None),
        job_id=int(getattr(application, "job_id")),
        status=str(getattr(application, "status", "")),
        support_level=str(getattr(application, "support_level", "")),
        support_rationale=str(getattr(application, "support_rationale", "")),
        notes=str(getattr(application, "notes", "")),
        last_preflight_detail=str(getattr(application, "last_preflight_detail", "")),
        last_submit_detail=str(getattr(application, "last_submit_detail", "")),
        last_error=str(getattr(application, "last_error", "")),
        created_at=getattr(application, "created_at", None),
        updated_at=getattr(application, "updated_at", None),
        submitted_at=getattr(application, "submitted_at", None),
        job=job_to_response(job) if job is not None else None,
    )


def application_event_to_response(event: object) -> ApplicationEventResponse:
    return ApplicationEventResponse(
        id=getattr(event, "id", None),
        application_id=int(getattr(event, "application_id")),
        event_type=str(getattr(event, "event_type", "")),
        detail=str(getattr(event, "detail", "")),
        from_status=getattr(event, "from_status", None),
        to_status=getattr(event, "to_status", None),
        created_at=getattr(event, "created_at", None),
    )
