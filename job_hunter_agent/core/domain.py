from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


VALID_STATUSES = {"collected", "approved", "rejected", "error_collect"}
VALID_APPLICATION_STATUSES = {
    "draft",
    "ready_for_review",
    "confirmed",
    "authorized_submit",
    "submitted",
    "error_submit",
    "cancelled",
}
VALID_APPLICATION_SUPPORT_LEVELS = {
    "auto_supported",
    "manual_review",
    "unsupported",
}


@dataclass(frozen=True)
class SiteConfig:
    name: str
    search_url: str
    enabled: bool = True


@dataclass(frozen=True)
class JobPosting:
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
    id: Optional[int] = None
    status: str = "collected"
    created_at: Optional[str] = None


@dataclass(frozen=True)
class RawJob:
    title: str
    company: str
    location: str
    work_mode: str
    salary_text: str
    url: str
    source_site: str
    summary: str
    description: str


@dataclass(frozen=True)
class ScoredJob:
    relevance: int
    rationale: str
    accepted: bool


@dataclass(frozen=True)
class CollectionRun:
    id: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: str = "running"
    jobs_seen: int = 0
    jobs_saved: int = 0
    errors: int = 0


@dataclass(frozen=True)
class CollectionReport:
    jobs: tuple[JobPosting, ...]
    jobs_seen: int
    jobs_saved: int
    errors: int


@dataclass(frozen=True)
class JobApplication:
    job_id: int
    status: str = "draft"
    id: Optional[int] = None
    support_level: str = "manual_review"
    support_rationale: str = ""
    notes: str = ""
    last_error: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    submitted_at: Optional[str] = None


@dataclass(frozen=True)
class JobApplicationEvent:
    application_id: int
    event_type: str
    detail: str = ""
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[str] = None
