from __future__ import annotations

from job_hunter_agent.core.browser_support import extract_json_object
from job_hunter_agent.core.matching import MatchingCriteria
from job_hunter_agent.core.domain import RawJob, ScoredJob


class HybridJobScorer:
    def __init__(self, model_name: str, base_url: str) -> None:
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de scoring nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc
        self._llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1)

    def score(self, raw_job: RawJob, criteria: MatchingCriteria) -> ScoredJob:
        combined_text = f"{raw_job.title} {raw_job.summary} {raw_job.description}".lower()
        if any(keyword in combined_text for keyword in criteria.exclude_keywords):
            return ScoredJob(relevance=1, rationale="Contem termos excluidos do perfil.", accepted=False)

        prompt = f"""
        Avalie aderencia de uma vaga ao perfil profissional abaixo.

        Perfil:
        {criteria.profile_text}

        Regras:
        - Nota de 1 a 10.
        - Considere palavras positivas: {", ".join(criteria.include_keywords)}
        - Considere palavras negativas: {", ".join(criteria.exclude_keywords)}
        - Modalidades aceitas: {", ".join(criteria.accepted_work_modes) or "qualquer"}
        - Salario minimo em BRL: {criteria.minimum_salary_brl}
        - Seja conservador. So aprove quando a vaga realmente fizer sentido.

        Vaga:
        titulo: {raw_job.title}
        empresa: {raw_job.company}
        local: {raw_job.location}
        modalidade: {raw_job.work_mode}
        salario: {raw_job.salary_text}
        resumo: {raw_job.summary}
        descricao: {raw_job.description}

        Retorne apenas JSON:
        {{
          "relevance": 7,
          "rationale": "motivo curto em portugues"
        }}
        """

        response = self._llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)
        return parse_scoring_response(response_text, criteria.minimum_relevance)


def parse_scoring_response(response_text: str, minimum_relevance: int) -> ScoredJob:
    payload = extract_json_object(response_text)
    if not payload:
        return ScoredJob(
            relevance=1,
            rationale="Resposta do modelo sem JSON valido.",
            accepted=False,
        )

    try:
        relevance = int(payload.get("relevance", 0) or 0)
    except (TypeError, ValueError):
        relevance = 0

    relevance = max(1, min(relevance, 10))
    rationale = str(payload.get("rationale", "")).strip() or "Sem justificativa do modelo."
    accepted = relevance >= minimum_relevance
    return ScoredJob(relevance=relevance, rationale=rationale, accepted=accepted)


def parse_salary_floor(salary_text: str) -> int | None:
    normalized = salary_text.lower().replace(".", "").replace(",", ".")
    import re

    matches = re.findall(r"(\d{3,6}(?:\.\d{1,2})?)", normalized)
    if not matches:
        return None
    try:
        first_value = float(matches[0])
    except ValueError:
        return None
    return int(first_value)


def standardize_error_message(error_type: str, site_name: str, detail: str) -> str:
    return f"{error_type} | site={site_name} | detalhe={detail}"
