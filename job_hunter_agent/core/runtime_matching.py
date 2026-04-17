from __future__ import annotations

from dataclasses import dataclass

from job_hunter_agent.core.matching_reasons import (
    REASON_EXCLUDED_KEYWORDS,
    REASON_SALARY_BELOW_MINIMUM,
    REASON_SENIORITY_OUTSIDE_TARGET,
    REASON_UNKNOWN_SENIORITY,
    REASON_WORK_MODE_MISMATCH,
)
from job_hunter_agent.core.seniority import infer_seniority_from_text, normalize_seniority_label
from job_hunter_agent.core.structured_matching_config import StructuredMatchingSource


@dataclass(frozen=True)
class RuntimeMatchingProfile:
    candidate_summary: str
    include_keywords: tuple[str, ...]
    exclude_keywords: tuple[str, ...]
    accepted_work_modes: tuple[str, ...]
    minimum_salary_brl: int
    minimum_relevance: int
    target_seniorities: tuple[str, ...] = ()
    allow_unknown_seniority: bool = True


@dataclass(frozen=True)
class RuntimeMatchingPolicy:
    profile: RuntimeMatchingProfile

    def contains_excluded_keywords(self, text: str) -> bool:
        normalized = text.lower()
        return any(keyword in normalized for keyword in self.profile.exclude_keywords)

    def accepts_work_mode(self, work_mode: str) -> bool:
        normalized = work_mode.strip().lower()
        if not normalized or normalized in {"nao informado", "nÃ£o informado"}:
            return True
        if not self.profile.accepted_work_modes:
            return True
        return any(mode in normalized for mode in self.profile.accepted_work_modes)

    def accepts_salary_floor(self, salary_floor: int | None) -> bool:
        if salary_floor is None:
            return True
        return salary_floor >= self.profile.minimum_salary_brl

    def accepts_relevance(self, relevance: int) -> bool:
        return relevance >= self.profile.minimum_relevance

    def evaluate_seniority_reason(self, text: str) -> str | None:
        if not self.profile.target_seniorities:
            return None
        detected = infer_seniority_from_text(text)
        if detected == "nao_informada":
            return None if self.profile.allow_unknown_seniority else REASON_UNKNOWN_SENIORITY
        accepted = {normalize_seniority_label(value) for value in self.profile.target_seniorities}
        return None if detected in accepted else REASON_SENIORITY_OUTSIDE_TARGET

    def evaluate_prefilter_reason(self, *, text: str, work_mode: str, salary_floor: int | None) -> str | None:
        if self.contains_excluded_keywords(text):
            return REASON_EXCLUDED_KEYWORDS
        seniority_reason = self.evaluate_seniority_reason(text)
        if seniority_reason is not None:
            return seniority_reason
        if not self.accepts_work_mode(work_mode):
            return REASON_WORK_MODE_MISMATCH
        if not self.accepts_salary_floor(salary_floor):
            return REASON_SALARY_BELOW_MINIMUM
        return None


def build_runtime_matching_profile_from_structured_source(
    *,
    structured_matching_source: StructuredMatchingSource,
    relaxed_matching_for_testing: bool,
    relaxed_testing_profile_hint: str,
    relaxed_testing_remove_exclude_keywords: tuple[str, ...],
    relaxed_testing_minimum_relevance: int,
) -> RuntimeMatchingProfile:
    candidate_summary = structured_matching_source.profile.summary
    exclude_keywords = structured_matching_source.matching.exclude_keywords
    minimum_relevance = structured_matching_source.matching.minimum_relevance

    if relaxed_matching_for_testing:
        candidate_summary = f"{candidate_summary} {relaxed_testing_profile_hint}".strip()
        blocked = {keyword.lower() for keyword in relaxed_testing_remove_exclude_keywords}
        exclude_keywords = tuple(keyword for keyword in exclude_keywords if keyword.lower() not in blocked)
        minimum_relevance = relaxed_testing_minimum_relevance

    return RuntimeMatchingProfile(
        candidate_summary=candidate_summary,
        include_keywords=structured_matching_source.matching.include_keywords,
        exclude_keywords=exclude_keywords,
        accepted_work_modes=structured_matching_source.matching.accepted_work_modes,
        minimum_salary_brl=structured_matching_source.matching.minimum_salary_brl,
        minimum_relevance=minimum_relevance,
        target_seniorities=structured_matching_source.matching.target_seniorities,
        allow_unknown_seniority=structured_matching_source.matching.allow_unknown_seniority,
    )


def runtime_rejection_reason_to_rationale(reason: str) -> str:
    mapping = {
        REASON_EXCLUDED_KEYWORDS: "termos_excluidos",
        REASON_SENIORITY_OUTSIDE_TARGET: "senioridade_fora_do_alvo",
        REASON_UNKNOWN_SENIORITY: "senioridade_nao_informada",
        REASON_WORK_MODE_MISMATCH: "modalidade_incompativel",
        REASON_SALARY_BELOW_MINIMUM: "salario_abaixo",
    }
    return mapping.get(reason, "sinais_insuficientes")
