from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from job_hunter_agent.domain import JobApplication, JobPosting
from job_hunter_agent.repository import JobRepository


@dataclass(frozen=True)
class ApplicationSubmissionResult:
    status: str
    detail: str
    submitted_at: Optional[str] = None
    external_reference: str = ""


class JobApplicant(Protocol):
    def submit(self, application: JobApplication, job: JobPosting) -> ApplicationSubmissionResult:
        raise NotImplementedError


class ApplicationPreparationService:
    def __init__(self, repository: JobRepository) -> None:
        self.repository = repository

    def create_drafts_for_approved_jobs(self, job_ids: list[int], notes: str = "") -> list[JobApplication]:
        drafts: list[JobApplication] = []
        for job_id in job_ids:
            job = self.repository.get_job(job_id)
            if not job or job.status != "approved":
                continue
            drafts.append(self.repository.create_application_draft(job_id, notes=notes))
        return drafts
