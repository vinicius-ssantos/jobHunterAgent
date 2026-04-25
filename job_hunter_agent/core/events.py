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


def event_to_dict(event: JobCollectedV1 | JobScoredV1) -> dict[str, Any]:
    return asdict(event)


def event_to_json(event: JobCollectedV1 | JobScoredV1) -> str:
    return json.dumps(event_to_dict(event), ensure_ascii=False, separators=(",", ":"))


def event_from_json(payload: str) -> JobCollectedV1 | JobScoredV1:
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise ValueError("Evento deve ser um objeto JSON.")
    return event_from_dict(decoded)


def event_from_dict(payload: dict[str, Any]) -> JobCollectedV1 | JobScoredV1:
    event_type = str(payload.get("event_type") or "").strip()
    if event_type == "JobCollectedV1" or _looks_like_legacy_job_collected(payload):
        return job_collected_from_dict(payload)
    if event_type == "JobScoredV1" or _looks_like_legacy_job_scored(payload):
        return job_scored_from_dict(payload)
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
        accepted=bool(payload.get("accepted")),
        relevance=_safe_int(payload.get("relevance")),
        event_id=_safe_str(payload.get("event_id")) or new_event_id(),
        event_type="JobScoredV1",
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
