from __future__ import annotations

from job_hunter_agent.application.contracts import (
    ApplicationFlowInspection,
    ApplicationSubmissionResult,
    InspectionPort,
    PreparationPort,
    SubmitPort,
)
from job_hunter_agent.core.domain import JobPosting


def normalize_application_flow_inspection(result) -> ApplicationFlowInspection:
    outcome = str(getattr(result, "outcome", "") or "").strip()
    detail = str(getattr(result, "detail", "") or "").strip()
    if outcome not in {"ready", "manual_review", "blocked", "ignored", "error"}:
        return ApplicationFlowInspection(
            outcome="error",
            detail="inspecao de fluxo retornou outcome invalido",
        )
    if not detail:
        return ApplicationFlowInspection(
            outcome="error",
            detail="inspecao de fluxo retornou detail vazio",
        )
    return ApplicationFlowInspection(outcome=outcome, detail=detail)


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
