from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from job_hunter_agent.core.domain import JobApplication, JobPosting


@dataclass(frozen=True)
class ApplicationSubmissionResult:
    status: str
    detail: str
    submitted_at: Optional[str] = None
    external_reference: str = ""


@dataclass(frozen=True)
class ApplicationFlowInspection:
    outcome: str
    detail: str


class ArtifactCapturePort(Protocol):
    async def capture(
        self,
        page,
        *,
        state,
        job: JobPosting,
        phase: str,
        detail: str,
    ) -> str: ...

    async def build_submit_exception_result(
        self,
        exc: Exception,
        *,
        page,
        state,
        job: JobPosting,
    ) -> ApplicationSubmissionResult: ...


class InspectionPort(Protocol):
    def inspect(self, job: JobPosting) -> ApplicationFlowInspection: ...


class SubmitPort(Protocol):
    def submit(self, application: JobApplication, job: JobPosting) -> ApplicationSubmissionResult: ...


class PreparationPort(Protocol):
    def create_drafts_for_approved_jobs(self, job_ids: list[int], notes: str = "") -> list[JobApplication]: ...
