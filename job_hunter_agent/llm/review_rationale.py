from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from job_hunter_agent.core.browser_support import extract_json_object
from job_hunter_agent.core.domain import JobPosting


@dataclass(frozen=True)
class StructuredReviewRationale:
    strengths: tuple[str, ...] = ()
    concerns: tuple[str, ...] = ()
    risk: str = ""


class ReviewRationaleFormatter(Protocol):
    def format(self, job: JobPosting) -> StructuredReviewRationale:
        raise NotImplementedError


class OllamaReviewRationaleFormatter:
    def __init__(self, model_name: str, base_url: str) -> None:
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de formatacao de rationale nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc
        self._llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1)

    def format(self, job: JobPosting) -> StructuredReviewRationale:
        response = self._llm.invoke(
            f"""
            Reestruture o motivo de revisao de uma vaga para leitura humana.

            Regras:
            - Responda apenas JSON.
            - Seja conciso.
            - Nao invente fatos ausentes.
            - Campos:
              - strengths: lista curta de pontos a favor
              - concerns: lista curta de pontos contra
              - risk: risco principal em uma frase curta

            Vaga:
            titulo: {job.title}
            empresa: {job.company}
            local: {job.location}
            modalidade: {job.work_mode}
            relevancia: {job.relevance}/10
            motivo atual: {job.rationale}
            resumo: {job.summary}

            Retorne apenas JSON:
            {{
              "strengths": ["..."],
              "concerns": ["..."],
              "risk": "..."
            }}
            """
        )
        response_text = response.content if hasattr(response, "content") else str(response)
        return parse_structured_review_rationale(response_text)


def parse_structured_review_rationale(response_text: str) -> StructuredReviewRationale:
    payload = extract_json_object(response_text)
    if not payload:
        return StructuredReviewRationale()
    return StructuredReviewRationale(
        strengths=_normalize_items(payload.get("strengths")),
        concerns=_normalize_items(payload.get("concerns")),
        risk=str(payload.get("risk", "")).strip(),
    )


def render_review_rationale(job: JobPosting, structured: StructuredReviewRationale | None = None) -> str:
    if not structured or (not structured.strengths and not structured.concerns and not structured.risk):
        return job.rationale

    lines: list[str] = []
    if structured.strengths:
        lines.append("Pontos a favor:")
        lines.extend(f"- {item}" for item in structured.strengths[:3])
    if structured.concerns:
        if lines:
            lines.append("")
        lines.append("Pontos contra:")
        lines.extend(f"- {item}" for item in structured.concerns[:3])
    if structured.risk:
        if lines:
            lines.append("")
        lines.append(f"Risco principal: {structured.risk}")
    return "\n".join(lines) or job.rationale


def _normalize_items(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    items: list[str] = []
    for item in value:
        normalized = str(item).strip()
        if normalized and normalized not in items:
            items.append(normalized)
    return tuple(items)
