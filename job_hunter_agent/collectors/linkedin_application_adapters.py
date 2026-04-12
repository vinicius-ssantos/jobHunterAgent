from __future__ import annotations

from pathlib import Path

from job_hunter_agent.application.contracts import (
    ApplicationFlowInspection,
    ApplicationSubmissionResult,
)


def _is_internal_linkedin_job(job) -> bool:
    return "linkedin.com/jobs/" in str(getattr(job, "url", "") or "").lower()


class LinkedInPreflightInspectorAdapter:
    def __init__(self, inspector, *, storage_state_path: str | Path | None = None) -> None:
        self._inspector = inspector
        self._storage_state_path = Path(storage_state_path).resolve() if storage_state_path else None

    def inspect(self, job):
        if not _is_internal_linkedin_job(job):
            return ApplicationFlowInspection(
                outcome="ignored",
                detail="vaga nao pertence ao fluxo interno do LinkedIn",
            )
        if self._storage_state_path is not None and not self._storage_state_path.exists():
            return ApplicationFlowInspection(
                outcome="error",
                detail="sessao autenticada do LinkedIn nao encontrada para inspecao real",
            )
        return self._inspector.inspect(job)


class LinkedInSubmissionApplicantAdapter:
    def __init__(self, inspector, *, storage_state_path: str | Path | None = None) -> None:
        self._inspector = inspector
        self._storage_state_path = Path(storage_state_path).resolve() if storage_state_path else None

    def submit(self, application, job):
        if not _is_internal_linkedin_job(job):
            return ApplicationSubmissionResult(
                status="error_submit",
                detail="submissao real indisponivel para vaga fora do LinkedIn interno",
            )
        if self._storage_state_path is not None and not self._storage_state_path.exists():
            return ApplicationSubmissionResult(
                status="error_submit",
                detail="sessao autenticada do LinkedIn nao encontrada para submissao real",
            )
        return self._inspector.submit(application, job)
