from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from job_hunter_agent.core.browser_support import extract_json_object
from job_hunter_agent.core.domain import JobPosting


@dataclass(frozen=True)
class ApplicationSupportAssessment:
    support_level: str
    rationale: str


class ApplicationSupportAssessor(Protocol):
    def assess(self, job: JobPosting) -> ApplicationSupportAssessment:
        raise NotImplementedError


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
