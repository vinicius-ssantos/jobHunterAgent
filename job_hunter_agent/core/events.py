from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any

from job_hunter_agent.core.domain import JobPosting


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_event_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class JobCollectedV1:
    run_id: int
    jobs: tuple[JobPosting, ...]
    jobs_seen: int
    jobs_saved: int
    errors: int
    event_id: str = field(default_factory=new_event_id)
    event_type: str = "JobCollectedV1"
    event_version: int = 1
    occurred_at: str = field(default_factory=utc_now_iso)
    correlation_id: str = ""


@dataclass(frozen=True)
class JobScoredV1:
    run_id: int
    external_key: str
    accepted: bool
    relevance: int
    event_id: str = field(default_factory=new_event_id)
    event_type: str = "JobScoredV1"
    event_version: int = 1
    occurred_at: str = field(default_factory=utc_now_iso)
    correlation_id: str = ""


@dataclass(frozen=True)
class JobReviewRequestedV1:
    job_id: int
    external_key: str
    source_site: str
    relevance: int
    reason: str = ""
    event_id: str = field(default_factory=new_event_id)
    event_type: str = "JobReviewRequestedV1"
    event_version: int = 1
    occurred_at: str = field(default_factory=utc_now_iso)
    correlation_id: str = ""


@dataclass(frozen=True)
class JobReviewedV1:
    job_id: int
    decision: str
    status: str
    reviewed_by: str = ""
    notes: str = ""
    external_key: str = ""
    event_id: str = field(default_factory=new_event_id)
    event_type: str = "JobReviewedV1"
    event_version: int = 1
    occurred_at: str = field(default_factory=utc_now_iso)
    correlation_id: str = ""


@dataclass(frozen=True)
class ApplicationAuthorizedV1:
    application_id: int
    job_id: int
    authorized_by: str = ""
    authorization_source: str = "manual"
    status: str = "authorized_submit"
    event_id: str = field(default_factory=new_event_id)
    event_type: str = "ApplicationAuthorizedV1"
    event_version: int = 1
    occurred_at: str = field(default_factory=utc_now_iso)
    correlation_id: str = ""


@dataclass(frozen=True)
class ApplicationPreflightCompletedV1:
    application_id: int
    job_id: int
    outcome: str
    application_status: str
    detail: str = ""
    event_id: str = field(default_factory=new_event_id)
    event_type: str = "ApplicationPreflightCompletedV1"
    event_version: int = 1
    occurred_at: str = field(default_factory=utc_now_iso)
    correlation_id: str = ""


@dataclass(frozen=True)
class ApplicationSubmittedV1:
    application_id: int
    job_id: int
    portal: str
    confirmation_reference: str = ""
    submitted_url: str = ""
    event_id: str = field(default_factory=new_event_id)
    event_type: str = "ApplicationSubmittedV1"
    event_version: int = 1
    occurred_at: str = field(default_factory=utc_now_iso)
    correlation_id: str = ""


@dataclass(frozen=True)
class ApplicationBlockedV1:
    application_id: int
    job_id: int
    reason: str
    detail: str = ""
    retryable: bool = False
    event_id: str = field(default_factory=new_event_id)
    event_type: str = "ApplicationBlockedV1"
    event_version: int = 1
    occurred_at: str = field(default_factory=utc_now_iso)
    correlation_id: str = ""


DomainEvent = (
    JobCollectedV1
    | JobScoredV1
    | JobReviewRequestedV1
    | JobReviewedV1
    | ApplicationAuthorizedV1
    | ApplicationPreflightCompletedV1
    | ApplicationSubmittedV1
    | ApplicationBlockedV1
)


def event_to_dict(event: DomainEvent) -> dict[str, Any]:
    return asdict(event)


def event_to_json(event: DomainEvent) -> str:
    return json.dumps(event_to_dict(event), ensure_ascii=False, separators=(",", ":"))


def event_from_json(payload: str) -> DomainEvent:
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise ValueError("Evento deve ser um objeto JSON.")
    return event_from_dict(decoded)


def event_from_dict(payload: dict[str, Any]) -> DomainEvent:
    event_type = str(payload.get("event_type") or "").strip()
    if event_type == "JobCollectedV1" or _looks_like_legacy_job_collected(payload):
        return job_collected_from_dict(payload)
    if event_type == "JobScoredV1" or _looks_like_legacy_job_scored(payload):
        return job_scored_from_dict(payload)
    if event_type == "JobReviewRequestedV1":
        return job_review_requested_from_dict(payload)
    if event_type == "JobReviewedV1":
        return job_reviewed_from_dict(payload)
    if event_type == "ApplicationAuthorizedV1":
        return application_authorized_from_dict(payload)
    if event_type == "ApplicationPreflightCompletedV1":
        return application_preflight_completed_from_dict(payload)
    if event_type == "ApplicationSubmittedV1":
        return application_submitted_from_dict(payload)
    if event_type == "ApplicationBlockedV1":
        return application_blocked_from_dict(payload)
    raise ValueError(f"Tipo de evento nao suportado: {event_type or '<ausente>'}")


def job_collected_from_dict(payload: dict[str, Any]) -> JobCollectedV1:
    jobs_payload = payload.get("jobs")
    if not isinstance(jobs_payload, list):
        jobs_payload = []
    return JobCollectedV1(
        run_id=_safe_int(payload.get("run_id")),
        jobs=tuple(_job_posting_from_dict(item) for item in jobs_payload if isinstance(item, dict)),
        jobs_seen=_safe_int(payload.get("jobs_seen")),
        jobs_saved=_safe_int(payload.get("jobs_saved")),
        errors=_safe_int(payload.get("errors")),
        event_id=_safe_str(payload.get("event_id")) or new_event_id(),
        event_type="JobCollectedV1",
        event_version=_safe_int(payload.get("event_version")) or 1,
        occurred_at=_safe_str(payload.get("occurred_at")) or utc_now_iso(),
        correlation_id=_safe_str(payload.get("correlation_id")),
    )


def job_scored_from_dict(payload: dict[str, Any]) -> JobScoredV1:
    return JobScoredV1(
        run_id=_safe_int(payload.get("run_id")),
        external_key=_safe_str(payload.get("external_key")),
        accepted=_safe_bool(payload.get("accepted")),
        relevance=_safe_int(payload.get("relevance")),
        event_id=_safe_str(payload.get("event_id")) or new_event_id(),
        event_type="JobScoredV1",
        event_version=_safe_int(payload.get("event_version")) or 1,
        occurred_at=_safe_str(payload.get("occurred_at")) or utc_now_iso(),
        correlation_id=_safe_str(payload.get("correlation_id")),
    )


def job_review_requested_from_dict(payload: dict[str, Any]) -> JobReviewRequestedV1:
    return JobReviewRequestedV1(
        job_id=_safe_int(payload.get("job_id")),
        external_key=_safe_str(payload.get("external_key")),
        source_site=_safe_str(payload.get("source_site")),
        relevance=_safe_int(payload.get("relevance")),
        reason=_safe_str(payload.get("reason")),
        event_id=_safe_str(payload.get("event_id")) or new_event_id(),
        event_type="JobReviewRequestedV1",
        event_version=_safe_int(payload.get("event_version")) or 1,
        occurred_at=_safe_str(payload.get("occurred_at")) or utc_now_iso(),
        correlation_id=_safe_str(payload.get("correlation_id")),
    )


def job_reviewed_from_dict(payload: dict[str, Any]) -> JobReviewedV1:
    return JobReviewedV1(
        job_id=_safe_int(payload.get("job_id")),
        decision=_safe_str(payload.get("decision")),
        status=_safe_str(payload.get("status")),
        reviewed_by=_safe_str(payload.get("reviewed_by")),
        notes=_safe_str(payload.get("notes")),
        external_key=_safe_str(payload.get("external_key")),
        event_id=_safe_str(payload.get("event_id")) or new_event_id(),
        event_type="JobReviewedV1",
        event_version=_safe_int(payload.get("event_version")) or 1,
        occurred_at=_safe_str(payload.get("occurred_at")) or utc_now_iso(),
        correlation_id=_safe_str(payload.get("correlation_id")),
    )


def application_authorized_from_dict(payload: dict[str, Any]) -> ApplicationAuthorizedV1:
    return ApplicationAuthorizedV1(
        application_id=_safe_int(payload.get("application_id")),
        job_id=_safe_int(payload.get("job_id")),
        authorized_by=_safe_str(payload.get("authorized_by")),
        authorization_source=_safe_str(payload.get("authorization_source")) or "manual",
        status=_safe_str(payload.get("status")) or "authorized_submit",
        event_id=_safe_str(payload.get("event_id")) or new_event_id(),
        event_type="ApplicationAuthorizedV1",
        event_version=_safe_int(payload.get("event_version")) or 1,
        occurred_at=_safe_str(payload.get("occurred_at")) or utc_now_iso(),
        correlation_id=_safe_str(payload.get("correlation_id")),
    )


def application_preflight_completed_from_dict(payload: dict[str, Any]) -> ApplicationPreflightCompletedV1:
    return ApplicationPreflightCompletedV1(
        application_id=_safe_int(payload.get("application_id")),
        job_id=_safe_int(payload.get("job_id")),
        outcome=_safe_str(payload.get("outcome")),
        application_status=_safe_str(payload.get("application_status")),
        detail=_safe_str(payload.get("detail")),
        event_id=_safe_str(payload.get("event_id")) or new_event_id(),
        event_type="ApplicationPreflightCompletedV1",
        event_version=_safe_int(payload.get("event_version")) or 1,
        occurred_at=_safe_str(payload.get("occurred_at")) or utc_now_iso(),
        correlation_id=_safe_str(payload.get("correlation_id")),
    )


def application_submitted_from_dict(payload: dict[str, Any]) -> ApplicationSubmittedV1:
    return ApplicationSubmittedV1(
        application_id=_safe_int(payload.get("application_id")),
        job_id=_safe_int(payload.get("job_id")),
        portal=_safe_str(payload.get("portal")),
        confirmation_reference=_safe_str(payload.get("confirmation_reference")),
        submitted_url=_safe_str(payload.get("submitted_url")),
        event_id=_safe_str(payload.get("event_id")) or new_event_id(),
        event_type="ApplicationSubmittedV1",
        event_version=_safe_int(payload.get("event_version")) or 1,
        occurred_at=_safe_str(payload.get("occurred_at")) or utc_now_iso(),
        correlation_id=_safe_str(payload.get("correlation_id")),
    )


def application_blocked_from_dict(payload: dict[str, Any]) -> ApplicationBlockedV1:
    return ApplicationBlockedV1(
        application_id=_safe_int(payload.get("application_id")),
        job_id=_safe_int(payload.get("job_id")),
        reason=_safe_str(payload.get("reason")),
        detail=_safe_str(payload.get("detail")),
        retryable=_safe_bool(payload.get("retryable")),
        event_id=_safe_str(payload.get("event_id")) or new_event_id(),
        event_type="ApplicationBlockedV1",
        event_version=_safe_int(payload.get("event_version")) or 1,
        occurred_at=_safe_str(payload.get("occurred_at")) or utc_now_iso(),
        correlation_id=_safe_str(payload.get("correlation_id")),
    )


def _job_posting_from_dict(payload: dict[str, Any]) -> JobPosting:
    allowed_fields = {item.name for item in fields(JobPosting)}
    normalized = {key: value for key, value in payload.items() if key in allowed_fields}
    required_defaults = {
        "title": "",
        "company": "",
        "location": "",
        "work_mode": "",
        "salary_text": "",
        "url": "",
        "source_site": "",
        "summary": "",
        "relevance": 0,
        "rationale": "",
        "external_key": "",
    }
    for key, value in required_defaults.items():
        normalized.setdefault(key, value)
    if "relevance" in normalized:
        normalized["relevance"] = _safe_int(normalized["relevance"])
    if "id" in normalized and normalized["id"] is not None:
        normalized["id"] = _safe_int(normalized["id"])
    return JobPosting(**normalized)


def _looks_like_legacy_job_collected(payload: dict[str, Any]) -> bool:
    return "jobs" in payload and "jobs_seen" in payload and "jobs_saved" in payload


def _looks_like_legacy_job_scored(payload: dict[str, Any]) -> bool:
    return "external_key" in payload and "accepted" in payload and "relevance" in payload


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "sim", "s"}
    return bool(value)


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 0
    return 0


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
