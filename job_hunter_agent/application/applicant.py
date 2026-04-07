from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from job_hunter_agent.application.application_flow import (
    ApplicationFlowCoordinator,
    load_application_context,
)
from job_hunter_agent.core.browser_support import extract_json_object
from job_hunter_agent.llm.application_priority import (
    ApplicationPriorityAssessor,
    DeterministicApplicationPriorityAssessor,
    format_application_priority_note,
)
from job_hunter_agent.core.domain import JobApplication, JobPosting
from job_hunter_agent.llm.job_requirements import (
    DeterministicJobRequirementsExtractor,
    JobRequirementSignals,
    JobRequirementsExtractor,
    format_job_requirement_signals,
)
from job_hunter_agent.infrastructure.repository import JobRepository


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


@dataclass(frozen=True)
class ApplicationSubmitResult:
    outcome: str
    detail: str
    application_status: str


class ApplicationSupportAssessor(Protocol):
    def assess(self, job: JobPosting) -> ApplicationSupportAssessment:
        raise NotImplementedError


class JobApplicant(Protocol):
    def submit(self, application: JobApplication, job: JobPosting) -> ApplicationSubmissionResult:
        raise NotImplementedError


class ApplicationFlowInspector(Protocol):
    def inspect(self, job: JobPosting):
        raise NotImplementedError


class ApplicationPreparationService:
    def __init__(
        self,
        repository: JobRepository,
        support_assessor: ApplicationSupportAssessor | None = None,
        requirements_extractor: JobRequirementsExtractor | None = None,
        priority_assessor: ApplicationPriorityAssessor | None = None,
    ) -> None:
        self.repository = repository
        self.support_assessor = support_assessor
        self.requirements_extractor = requirements_extractor
        self.priority_assessor = priority_assessor

    def create_drafts_for_approved_jobs(self, job_ids: list[int], notes: str = "") -> list[JobApplication]:
        drafts: list[JobApplication] = []
        for job_id in job_ids:
            job = self.repository.get_job(job_id)
            if not job or job.status != "approved":
                continue
            assessment = self._assess_support(job)
            note_bundle = self._build_requirement_notes(job)
            priority_note = self._build_priority_note(job)
            draft_notes = notes
            if note_bundle:
                draft_notes = _append_note(draft_notes, note_bundle)
            if priority_note:
                draft_notes = _append_note(draft_notes, priority_note)
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

    def _build_priority_note(self, job: JobPosting) -> str:
        fallback = DeterministicApplicationPriorityAssessor().assess(job)
        if self.priority_assessor is None:
            return format_application_priority_note(fallback)
        try:
            assessed = self.priority_assessor.assess(job)
        except Exception:
            assessed = fallback
        if assessed.level not in {"alta", "media", "baixa"}:
            assessed = fallback
        if not assessed.rationale.strip():
            assessed = fallback
        return format_application_priority_note(assessed)


class ApplicationPreflightService:
    def __init__(self, repository: JobRepository, flow_inspector: ApplicationFlowInspector | None = None) -> None:
        self.repository = repository
        self.flow_inspector = flow_inspector
        self.flow = ApplicationFlowCoordinator(repository)

    def run_for_application(self, application_id: int) -> ApplicationPreflightResult:
        context = load_application_context(self.repository, application_id)
        application = context.application
        job = context.job

        if application.status != "confirmed":
            detail = "preflight disponivel apenas para candidaturas confirmadas"
            self.flow.record_event(
                application.id,
                event_type="preflight_ignored",
                detail=detail,
                from_status=application.status,
                to_status=application.status,
            )
            return ApplicationPreflightResult(
                outcome="ignored",
                detail=detail,
                application_status=application.status,
            )

        if application.support_level == "unsupported":
            detail = "preflight bloqueado: fluxo classificado como nao suportado"
            application_status = self.flow.record_preflight_result(
                context,
                outcome="blocked",
                detail=detail,
                event_type="preflight_blocked",
                status="error_submit",
                clear_error=False,
            )
            return ApplicationPreflightResult(
                outcome="blocked",
                detail=detail,
                application_status=application_status,
            )

        if job.source_site.lower() == "linkedin" and "linkedin.com/jobs/" in job.url.lower():
            if self.flow_inspector is not None:
                try:
                    inspection = self.flow_inspector.inspect(job)
                except Exception as exc:
                    inspection = None
                    detail = f"preflight real falhou ao inspecionar a pagina: {exc}"
                    application_status = self.flow.record_preflight_result(
                        context,
                        outcome="error",
                        detail=detail,
                        event_type="preflight_error",
                        status="confirmed",
                        clear_error=True,
                    )
                    return ApplicationPreflightResult(
                        outcome="error",
                        detail=detail,
                        application_status=application_status,
                    )
                if inspection is not None:
                    if inspection.outcome == "ready":
                        application_status = self.flow.record_preflight_result(
                            context,
                            outcome="ready",
                            detail=inspection.detail,
                            event_type="preflight_ready",
                            status="confirmed",
                            clear_error=True,
                        )
                        return ApplicationPreflightResult(
                            outcome="ready",
                            detail=inspection.detail,
                            application_status=application_status,
                        )
                    if inspection.outcome == "manual_review":
                        application_status = self.flow.record_preflight_result(
                            context,
                            outcome="manual_review",
                            detail=inspection.detail,
                            event_type="preflight_manual_review",
                            status="confirmed",
                            clear_error=True,
                        )
                        return ApplicationPreflightResult(
                            outcome="manual_review",
                            detail=inspection.detail,
                            application_status=application_status,
                        )
                    detail = inspection.detail
                    application_status = self.flow.record_preflight_result(
                        context,
                        outcome="blocked",
                        detail=detail,
                        event_type="preflight_blocked",
                        status="error_submit",
                        clear_error=False,
                    )
                    return ApplicationPreflightResult(
                        outcome="blocked",
                        detail=detail,
                        application_status=application_status,
                    )
            if application.support_level == "auto_supported":
                detail = "preflight ok: fluxo do LinkedIn com indicio de candidatura simplificada"
            else:
                detail = "preflight ok: vaga interna do LinkedIn pronta para futura automacao assistida"
            application_status = self.flow.record_preflight_result(
                context,
                outcome="ready",
                detail=detail,
                event_type="preflight_ready",
                status="confirmed",
                clear_error=True,
            )
            return ApplicationPreflightResult(
                outcome="ready",
                detail=detail,
                application_status=application_status,
            )

        detail = "preflight bloqueado: portal ainda nao possui executor suportado"
        application_status = self.flow.record_preflight_result(
            context,
            outcome="blocked",
            detail=detail,
            event_type="preflight_blocked",
            status="error_submit",
            clear_error=False,
        )
        return ApplicationPreflightResult(
            outcome="blocked",
            detail=detail,
            application_status=application_status,
        )


class ApplicationSubmissionService:
    def __init__(self, repository: JobRepository, applicant: JobApplicant | None = None) -> None:
        self.repository = repository
        self.applicant = applicant
        self.flow = ApplicationFlowCoordinator(repository)

    def run_for_application(self, application_id: int) -> ApplicationSubmitResult:
        context = load_application_context(self.repository, application_id)
        application = context.application
        job = context.job

        if application.status != "authorized_submit":
            detail = "submissao real disponivel apenas para candidaturas autorizadas"
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

        if self.applicant is None:
            detail = "submissao real indisponivel nesta execucao"
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
            result = self.applicant.submit(application, job)
        except Exception as exc:
            detail = f"submissao real falhou ao executar o applicant: {exc}"
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

        detail = result.detail.strip() or "submissao real executada sem detalhe"
        if result.external_reference:
            detail = f"{detail} | referencia={result.external_reference}"

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
