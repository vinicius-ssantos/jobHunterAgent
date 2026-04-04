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


@dataclass(frozen=True)
class ApplicationSupportAssessment:
    support_level: str
    rationale: str


@dataclass(frozen=True)
class ApplicationPreflightResult:
    outcome: str
    detail: str
    application_status: str


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
            assessment = classify_job_application_support(job)
            drafts.append(
                self.repository.create_application_draft(
                    job_id,
                    notes=notes,
                    support_level=assessment.support_level,
                    support_rationale=assessment.rationale,
                )
            )
        return drafts


class ApplicationPreflightService:
    def __init__(self, repository: JobRepository) -> None:
        self.repository = repository

    def run_for_application(self, application_id: int) -> ApplicationPreflightResult:
        application = self.repository.get_application(application_id)
        if not application:
            raise ValueError(f"Application not found: {application_id}")
        job = self.repository.get_job(application.job_id)
        if not job:
            raise ValueError(f"Job not found for application: {application_id}")

        if application.status != "confirmed":
            detail = "preflight disponivel apenas para candidaturas confirmadas"
            return ApplicationPreflightResult(
                outcome="ignored",
                detail=detail,
                application_status=application.status,
            )

        if application.support_level == "unsupported":
            detail = "preflight bloqueado: fluxo classificado como nao suportado"
            self.repository.mark_application_status(
                application.id,
                status="error_submit",
                notes=_append_note(application.notes, detail),
                last_error=detail,
            )
            return ApplicationPreflightResult(
                outcome="blocked",
                detail=detail,
                application_status="error_submit",
            )

        if job.source_site.lower() == "linkedin" and "linkedin.com/jobs/" in job.url.lower():
            if application.support_level == "auto_supported":
                detail = "preflight ok: fluxo do LinkedIn com indicio de candidatura simplificada"
            else:
                detail = "preflight ok: vaga interna do LinkedIn pronta para futura automacao assistida"
            self.repository.mark_application_status(
                application.id,
                status="confirmed",
                notes=_append_note(application.notes, detail),
                last_error="",
            )
            return ApplicationPreflightResult(
                outcome="ready",
                detail=detail,
                application_status="confirmed",
            )

        detail = "preflight bloqueado: portal ainda nao possui executor suportado"
        self.repository.mark_application_status(
            application.id,
            status="error_submit",
            notes=_append_note(application.notes, detail),
            last_error=detail,
        )
        return ApplicationPreflightResult(
            outcome="blocked",
            detail=detail,
            application_status="error_submit",
        )


def classify_job_application_support(job: JobPosting) -> ApplicationSupportAssessment:
    normalized_url = job.url.lower()
    normalized_site = job.source_site.lower()
    normalized_summary = job.summary.lower()

    if "gupy.io" in normalized_url or normalized_site == "gupy":
        return ApplicationSupportAssessment(
            support_level="unsupported",
            rationale="portal externo com formulario proprio ainda nao suportado",
        )

    if "linkedin.com/jobs/view/" in normalized_url or normalized_site == "linkedin":
        if "easy apply" in normalized_summary or "candidatura simplificada" in normalized_summary:
            return ApplicationSupportAssessment(
                support_level="auto_supported",
                rationale="vaga no LinkedIn com indicio explicito de candidatura simplificada",
            )
        return ApplicationSupportAssessment(
            support_level="manual_review",
            rationale="vaga interna do LinkedIn sem evidencia suficiente de fluxo simplificado",
        )

    if "indeed.com" in normalized_url or normalized_site == "indeed":
        return ApplicationSupportAssessment(
            support_level="manual_review",
            rationale="fonte conhecida, mas sem automacao de candidatura implementada",
        )

    return ApplicationSupportAssessment(
        support_level="unsupported",
        rationale="fluxo de candidatura ainda nao classificado para suporte automatico",
    )


def _append_note(existing_notes: str, new_note: str) -> str:
    normalized_existing = existing_notes.strip()
    normalized_new = new_note.strip()
    if not normalized_existing:
        return normalized_new
    existing_lines = {line.strip() for line in normalized_existing.splitlines() if line.strip()}
    if normalized_new in existing_lines:
        return normalized_existing
    return f"{normalized_existing}\n{normalized_new}"
