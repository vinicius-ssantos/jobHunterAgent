from __future__ import annotations

from job_hunter_agent.core.browser_support import extract_json_object
from job_hunter_agent.core.matching import MatchingCriteria, MatchingPolicy
from job_hunter_agent.core.matching_prompt import build_legacy_scoring_prompt
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
        policy = MatchingPolicy(criteria)
        combined_text = f"{raw_job.title} {raw_job.summary} {raw_job.description}".lower()
        if policy.contains_excluded_keywords(combined_text):
            return ScoredJob(relevance=1, rationale="termos_excluidos", accepted=False)

        prompt = build_legacy_scoring_prompt(raw_job, criteria)
        response = self._llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)
        return parse_scoring_response(response_text, policy)


def parse_scoring_response(response_text: str, policy: MatchingPolicy | int) -> ScoredJob:
    payload = extract_json_object(response_text)
    if not payload:
        return ScoredJob(
            relevance=1,
            rationale="resposta_invalida",
            accepted=False,
        )

    try:
        relevance = int(payload.get("relevance", 0) or 0)
    except (TypeError, ValueError):
        relevance = 0

    relevance = max(1, min(relevance, 10))
    rationale = str(payload.get("rationale", "")).strip() or "sem_justificativa"
    if isinstance(policy, int):
        accepted = relevance >= policy
    else:
        accepted = policy.accepts_relevance(relevance)
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
