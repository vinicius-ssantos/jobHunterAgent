from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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


class ArtifactClockPort(Protocol):
    def filename_timestamp(self) -> str: ...

    def event_timestamp(self) -> str: ...


class ArtifactFilesystemPort(Protocol):
    def ensure_directory(self, path: Path) -> None: ...

    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None: ...

    def write_json(self, path: Path, payload: object, *, encoding: str = "utf-8") -> None: ...


class ArtifactIdGeneratorPort(Protocol):
    def next_short_id(self) -> str: ...


class InspectionPort(Protocol):
    def inspect(self, job: JobPosting) -> ApplicationFlowInspection: ...


class SubmitPort(Protocol):
    def submit(self, application: JobApplication, job: JobPosting) -> ApplicationSubmissionResult: ...


class PreparationPort(Protocol):
    def create_drafts_for_approved_jobs(self, job_ids: list[int], notes: str = "") -> list[JobApplication]: ...
