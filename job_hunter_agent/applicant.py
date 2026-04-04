from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from job_hunter_agent.domain import JobApplication, JobPosting


@dataclass(frozen=True)
class ApplicationSubmissionResult:
    status: str
    detail: str
    submitted_at: Optional[str] = None
    external_reference: str = ""


class JobApplicant(Protocol):
    def submit(self, application: JobApplication, job: JobPosting) -> ApplicationSubmissionResult:
        raise NotImplementedError
