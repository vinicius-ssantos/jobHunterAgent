from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from job_hunter_agent.core.browser_support import extract_json_object
from job_hunter_agent.core.domain import JobPosting


@dataclass(frozen=True)
class ApplicationPriorityAssessment:
    level: str
    rationale: str


class ApplicationPriorityAssessor(Protocol):
    def assess(self, job: JobPosting) -> ApplicationPriorityAssessment:
        raise NotImplementedError


class DeterministicApplicationPriorityAssessor:
    def __init__(
        self,
        *,
        high_min_relevance: int = 8,
        medium_min_relevance: int = 6,
        preferred_work_modes: tuple[str, ...] = ("remoto", "hibrido", "hybrid", "remote"),
    ) -> None:
        self._high_min_relevance = high_min_relevance
        self._medium_min_relevance = medium_min_relevance
        self._preferred_work_modes = tuple(mode.strip().lower() for mode in preferred_work_modes if mode.strip())

    def assess(self, job: JobPosting) -> ApplicationPriorityAssessment:
        normalized_work_mode = job.work_mode.lower()
        has_preferred_work_mode = any(mode in normalized_work_mode for mode in self._preferred_work_modes)
        if job.relevance >= self._high_min_relevance and has_preferred_work_mode:
            return ApplicationPriorityAssessment(
                level="alta",
                rationale="relevancia alta com modalidade favoravel",
            )
        if job.relevance >= self._medium_min_relevance:
            return ApplicationPriorityAssessment(
                level="media",
                rationale="vaga promissora, mas requer revisao mais cuidadosa",
            )
        return ApplicationPriorityAssessment(
            level="baixa",
            rationale="aderencia moderada ou sinais insuficientes para priorizacao alta",
        )


class OllamaApplicationPriorityAssessor:
    def __init__(self, model_name: str, base_url: str) -> None:
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de priorizacao de candidatura nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc
        self._llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1)

    def assess(self, job: JobPosting) -> ApplicationPriorityAssessment:
        response = self._llm.invoke(
            f"""
            Sugira a prioridade operacional de revisao/candidatura de uma vaga.

            Regras:
            - Responda apenas JSON.
            - Escolha exatamente um level entre: alta, media, baixa.
            - Seja conservador.
            - Nao invente fatos ausentes.
            - rationale deve ser curto e em portugues.

            Vaga:
            titulo: {job.title}
            empresa: {job.company}
            local: {job.location}
            modalidade: {job.work_mode}
            relevancia: {job.relevance}/10
            motivo: {job.rationale}
            resumo: {job.summary}

            Retorne apenas JSON:
            {{
              "level": "media",
              "rationale": "motivo curto em portugues"
            }}
            """
        )
        response_text = response.content if hasattr(response, "content") else str(response)
        return parse_application_priority_response(response_text)


def parse_application_priority_response(response_text: str) -> ApplicationPriorityAssessment:
    payload = extract_json_object(response_text)
    if not payload:
        return ApplicationPriorityAssessment(level="baixa", rationale="resposta do modelo sem JSON valido")
    level = str(payload.get("level", "")).strip().lower()
    if level not in {"alta", "media", "baixa"}:
        return ApplicationPriorityAssessment(level="baixa", rationale="modelo retornou nivel invalido")
    rationale = str(payload.get("rationale", "")).strip() or "sem justificativa do modelo"
    return ApplicationPriorityAssessment(level=level, rationale=rationale)


def format_application_priority_note(assessment: ApplicationPriorityAssessment) -> str:
    return f"prioridade sugerida: {assessment.level} | motivo: {assessment.rationale}"


def extract_application_priority_level(notes: str) -> str:
    normalized = notes.lower()
    if "prioridade sugerida: alta" in normalized:
        return "alta"
    if "prioridade sugerida: media" in normalized:
        return "media"
    return "baixa"
