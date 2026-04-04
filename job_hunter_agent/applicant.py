from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from job_hunter_agent.browser_support import extract_json_object
from job_hunter_agent.domain import JobApplication, JobPosting
from job_hunter_agent.job_requirements import (
    DeterministicJobRequirementsExtractor,
    JobRequirementSignals,
    JobRequirementsExtractor,
    format_job_requirement_signals,
)
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


class ApplicationSupportAssessor(Protocol):
    def assess(self, job: JobPosting) -> ApplicationSupportAssessment:
        raise NotImplementedError


class JobApplicant(Protocol):
    def submit(self, application: JobApplication, job: JobPosting) -> ApplicationSubmissionResult:
        raise NotImplementedError


class ApplicationPreparationService:
    def __init__(
        self,
        repository: JobRepository,
        support_assessor: ApplicationSupportAssessor | None = None,
        requirements_extractor: JobRequirementsExtractor | None = None,
    ) -> None:
        self.repository = repository
        self.support_assessor = support_assessor
        self.requirements_extractor = requirements_extractor

    def create_drafts_for_approved_jobs(self, job_ids: list[int], notes: str = "") -> list[JobApplication]:
        drafts: list[JobApplication] = []
        for job_id in job_ids:
            job = self.repository.get_job(job_id)
            if not job or job.status != "approved":
                continue
            assessment = self._assess_support(job)
            note_bundle = self._build_requirement_notes(job)
            draft_notes = _append_note(notes, note_bundle) if note_bundle else notes
            drafts.append(
                self.repository.create_application_draft(
                    job_id,
                    notes=draft_notes,
                    support_level=assessment.support_level,
                    support_rationale=assessment.rationale,
                )
            )
        return drafts

    def _assess_support(self, job: JobPosting) -> ApplicationSupportAssessment:
        fallback = classify_job_application_support(job)
        if self.support_assessor is None:
            return fallback
        try:
            assessed = self.support_assessor.assess(job)
        except Exception:
            return fallback
        if assessed.support_level not in {"auto_supported", "manual_review", "unsupported"}:
            return fallback
        rationale = assessed.rationale.strip()
        if not rationale:
            return fallback
        return ApplicationSupportAssessment(
            support_level=assessed.support_level,
            rationale=rationale,
        )

    def _build_requirement_notes(self, job: JobPosting) -> str:
        fallback = DeterministicJobRequirementsExtractor().extract(job)
        if self.requirements_extractor is None:
            return format_job_requirement_signals(fallback)
        try:
            extracted = self.requirements_extractor.extract(job)
        except Exception:
            extracted = fallback
        return format_job_requirement_signals(self._merge_requirement_signals(fallback, extracted))

    @staticmethod
    def _merge_requirement_signals(
        fallback: JobRequirementSignals,
        extracted: JobRequirementSignals,
    ) -> JobRequirementSignals:
        return JobRequirementSignals(
            seniority=extracted.seniority if extracted.seniority != "nao_informada" else fallback.seniority,
            primary_stack=extracted.primary_stack or fallback.primary_stack,
            secondary_stack=extracted.secondary_stack or fallback.secondary_stack,
            english_level=(
                extracted.english_level
                if extracted.english_level != "nao_informado"
                else fallback.english_level
            ),
            leadership_signals=extracted.leadership_signals or fallback.leadership_signals,
            rationale=extracted.rationale or fallback.rationale,
        )


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


class OllamaApplicationSupportAssessor:
    def __init__(self, model_name: str, base_url: str) -> None:
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de classificacao de candidatura nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc
        self._llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1)

    def assess(self, job: JobPosting) -> ApplicationSupportAssessment:
        response = self._llm.invoke(
            f"""
            Classifique a aplicabilidade automatica de uma candidatura.

            Regras:
            - Responda apenas JSON.
            - Escolha exatamente um support_level entre:
              - auto_supported
              - manual_review
              - unsupported
            - Seja conservador.
            - So use auto_supported se houver evidencia de fluxo simples e previsivel.
            - Nunca invente sinais ausentes.
            - O rationale deve ser curto e em portugues.

            Vaga:
            titulo: {job.title}
            empresa: {job.company}
            local: {job.location}
            site: {job.source_site}
            url: {job.url}
            resumo: {job.summary}

            Retorne apenas JSON:
            {{
              "support_level": "manual_review",
              "rationale": "motivo curto em portugues"
            }}
            """
        )
        response_text = response.content if hasattr(response, "content") else str(response)
        return parse_application_support_response(response_text)


def parse_application_support_response(response_text: str) -> ApplicationSupportAssessment:
    payload = extract_json_object(response_text)
    if not payload:
        return ApplicationSupportAssessment(
            support_level="unsupported",
            rationale="resposta do modelo sem JSON valido",
        )

    support_level = str(payload.get("support_level", "")).strip()
    rationale = str(payload.get("rationale", "")).strip() or "sem justificativa do modelo"
    if support_level not in {"auto_supported", "manual_review", "unsupported"}:
        return ApplicationSupportAssessment(
            support_level="unsupported",
            rationale="modelo retornou support_level invalido",
        )
    return ApplicationSupportAssessment(
        support_level=support_level,
        rationale=rationale,
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
