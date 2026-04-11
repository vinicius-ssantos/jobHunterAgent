from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from job_hunter_agent.application.application_flow import (
    ApplicationFlowCoordinator,
    load_application_context,
)
from job_hunter_agent.application.application_messages import (
    format_submit_applicant_error,
    format_submit_detail,
    format_submit_portal_not_supported,
    format_submit_readiness_incomplete,
    format_submit_requires_authorized_status,
    format_submit_unavailable_in_execution,
)
from job_hunter_agent.application.application_notes import append_note
from job_hunter_agent.application.application_readiness import ApplicationReadinessCheckService
from job_hunter_agent.application.contracts import ApplicationSubmissionResult
from job_hunter_agent.core.domain import JobApplication, JobPosting
from job_hunter_agent.core.portal_capabilities import get_portal_capabilities
from job_hunter_agent.infrastructure.repository import JobRepository


@dataclass(frozen=True)
class ApplicationSubmitResult:
    outcome: str
    detail: str
    application_status: str


class JobApplicant(Protocol):
    def submit(self, application: JobApplication, job: JobPosting) -> ApplicationSubmissionResult:
        raise NotImplementedError


def normalize_application_submission_result(result) -> ApplicationSubmissionResult:
    status = str(getattr(result, "status", "") or "").strip()
    detail = str(getattr(result, "detail", "") or "").strip()
    submitted_at_raw = getattr(result, "submitted_at", None)
    external_reference_raw = getattr(result, "external_reference", "")
    if status not in {"submitted", "error_submit", "authorized_submit"}:
        return ApplicationSubmissionResult(
            status="error_submit",
            detail="applicant retornou status invalido",
        )
    if not detail:
        return ApplicationSubmissionResult(
            status="error_submit",
            detail="applicant retornou detail vazio",
        )
    submitted_at = str(submitted_at_raw).strip() if submitted_at_raw else None
    external_reference = str(external_reference_raw or "").strip()
    return ApplicationSubmissionResult(
        status=status,
        detail=detail,
        submitted_at=submitted_at,
        external_reference=external_reference,
    )


class ApplicationSubmissionService:
    def __init__(
        self,
        repository: JobRepository,
        applicant: JobApplicant | None = None,
        readiness_checker: ApplicationReadinessCheckService | None = None,
    ) -> None:
        self.repository = repository
        self.applicant = applicant
        self.flow = ApplicationFlowCoordinator(repository)
        self.readiness_checker = readiness_checker

    def run_for_application(self, application_id: int) -> ApplicationSubmitResult:
        context = load_application_context(self.repository, application_id)
        application = context.application
        job = context.job

        if application.status != "authorized_submit":
            detail = format_submit_requires_authorized_status()
            self.flow.record_event(
                application.id,
                event_type="submit_ignored",
                detail=detail,
                from_status=application.status,
                to_status=application.status,
            )
            return ApplicationSubmitResult(
                outcome="ignored",
                detail=detail,
                application_status=application.status,
            )

        capabilities = get_portal_capabilities(job)
        if not capabilities.submit_supported:
            detail = format_submit_portal_not_supported(portal_name=capabilities.portal_name)
            self.repository.mark_application_status(
                application.id,
                status="error_submit",
                notes=append_note(application.notes, detail),
                last_error=detail,
            )
            return ApplicationSubmitResult(
                outcome="blocked",
                detail=detail,
                application_status="error_submit",
            )

        if self.readiness_checker is not None:
            readiness = self.readiness_checker.check_submit_ready(job)
            if not readiness.ok:
                detail = format_submit_readiness_incomplete(failures=readiness.failures)
                self.repository.mark_application_status(
                    application.id,
                    status="authorized_submit",
                    notes=append_note(application.notes, detail),
                    last_error="",
                )
                return ApplicationSubmitResult(
                    outcome="ignored",
                    detail=detail,
                    application_status="authorized_submit",
                )

        if self.applicant is None:
            detail = format_submit_unavailable_in_execution()
            application_status = self.flow.record_submit_result(
                context,
                detail=detail,
                event_type="submit_ignored",
                status="authorized_submit",
                clear_error=True,
            )
            return ApplicationSubmitResult(
                outcome="ignored",
                detail=detail,
                application_status=application_status,
            )

        try:
            result = normalize_application_submission_result(self.applicant.submit(application, job))
        except Exception as exc:
            detail = format_submit_applicant_error(exc)
            application_status = self.flow.record_submit_result(
                context,
                detail=detail,
                event_type="submit_error",
                status="error_submit",
                clear_error=False,
            )
            return ApplicationSubmitResult(
                outcome="error",
                detail=detail,
                application_status=application_status,
            )

        detail = format_submit_detail(detail=result.detail, external_reference=result.external_reference)

        if result.status == "submitted":
            application_status = self.flow.record_submit_result(
                context,
                detail=detail,
                event_type="submit_submitted",
                status="submitted",
                clear_error=True,
                submitted_at=self.flow.resolve_submitted_at(result.submitted_at),
            )
            return ApplicationSubmitResult(
                outcome="submitted",
                detail=detail,
                application_status=application_status,
            )

        application_status = self.flow.record_submit_result(
            context,
            detail=detail,
            event_type="submit_error",
            status="error_submit",
            clear_error=False,
        )
        return ApplicationSubmitResult(
            outcome="error",
            detail=detail,
            application_status=application_status,
        )
