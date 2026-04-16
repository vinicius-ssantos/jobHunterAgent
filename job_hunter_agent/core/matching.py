from __future__ import annotations

from dataclasses import dataclass

from job_hunter_agent.core.legacy_matching_config import LegacyMatchingConfig
from job_hunter_agent.core.matching_reasons import (
    REASON_SENIORITY_OUTSIDE_TARGET,
    REASON_UNKNOWN_SENIORITY,
)
from job_hunter_agent.core.seniority import infer_seniority_from_text, normalize_seniority_label
from job_hunter_agent.core.structured_matching_config import StructuredMatchingSource


@dataclass(frozen=True)
class MatchingCriteria:
    profile_text: str
    include_keywords: tuple[str, ...]
    exclude_keywords: tuple[str, ...]
    accepted_work_modes: tuple[str, ...]
    minimum_salary_brl: int
    minimum_relevance: int
    target_seniorities: tuple[str, ...] = ()
    allow_unknown_seniority: bool = True


@dataclass(frozen=True)
class MatchingPolicy:
    criteria: MatchingCriteria

    def contains_excluded_keywords(self, text: str) -> bool:
        normalized = text.lower()
        return any(keyword in normalized for keyword in self.criteria.exclude_keywords)

    def accepts_work_mode(self, work_mode: str) -> bool:
        normalized = work_mode.strip().lower()
        if not normalized or normalized in {"nao informado", "nÃ£o informado"}:
            return True
        if not self.criteria.accepted_work_modes:
            return True
        return any(mode in normalized for mode in self.criteria.accepted_work_modes)

    def accepts_salary_floor(self, salary_floor: int | None) -> bool:
        if salary_floor is None:
            return True
        return salary_floor >= self.criteria.minimum_salary_brl

    def accepts_relevance(self, relevance: int) -> bool:
        return relevance >= self.criteria.minimum_relevance

    def evaluate_seniority_reason(self, text: str) -> str | None:
        if not self.criteria.target_seniorities:
            return None
        detected = infer_seniority_from_text(text)
        if detected == "nao_informada":
            return None if self.criteria.allow_unknown_seniority else REASON_UNKNOWN_SENIORITY
        accepted = {normalize_seniority_label(value) for value in self.criteria.target_seniorities}
        return None if detected in accepted else REASON_SENIORITY_OUTSIDE_TARGET


def build_matching_criteria(
    *,
    profile_text: str,
    include_keywords: tuple[str, ...],
    exclude_keywords: tuple[str, ...],
    accepted_work_modes: tuple[str, ...],
    minimum_salary_brl: int,
    minimum_relevance: int,
    relaxed_matching_for_testing: bool,
    relaxed_testing_profile_hint: str,
    relaxed_testing_remove_exclude_keywords: tuple[str, ...],
    relaxed_testing_minimum_relevance: int,
    target_seniorities: tuple[str, ...] = (),
    allow_unknown_seniority: bool = True,
) -> MatchingCriteria:
    resolved_profile_text = profile_text
    resolved_exclude_keywords = exclude_keywords
    resolved_minimum_relevance = minimum_relevance

    if relaxed_matching_for_testing:
        resolved_profile_text = f"{profile_text} {relaxed_testing_profile_hint}".strip()
        blocked = {keyword.lower() for keyword in relaxed_testing_remove_exclude_keywords}
        resolved_exclude_keywords = tuple(
            keyword for keyword in exclude_keywords if keyword.lower() not in blocked
        )
        resolved_minimum_relevance = relaxed_testing_minimum_relevance

    return MatchingCriteria(
        profile_text=resolved_profile_text,
        include_keywords=include_keywords,
        exclude_keywords=resolved_exclude_keywords,
        accepted_work_modes=accepted_work_modes,
        minimum_salary_brl=minimum_salary_brl,
        minimum_relevance=resolved_minimum_relevance,
        target_seniorities=target_seniorities,
        allow_unknown_seniority=allow_unknown_seniority,
    )


def build_matching_criteria_from_legacy_config(
    *,
    legacy_matching: LegacyMatchingConfig,
    relaxed_matching_for_testing: bool,
    relaxed_testing_profile_hint: str,
    relaxed_testing_remove_exclude_keywords: tuple[str, ...],
    relaxed_testing_minimum_relevance: int,
) -> MatchingCriteria:
    inferred = infer_seniority_from_text(legacy_matching.profile_text)
    target_seniorities = () if inferred == "nao_informada" else (inferred,)
    return build_matching_criteria(
        profile_text=legacy_matching.profile_text,
        include_keywords=legacy_matching.include_keywords,
        exclude_keywords=legacy_matching.exclude_keywords,
        accepted_work_modes=legacy_matching.accepted_work_modes,
        minimum_salary_brl=legacy_matching.minimum_salary_brl,
        minimum_relevance=legacy_matching.minimum_relevance,
        relaxed_matching_for_testing=relaxed_matching_for_testing,
        relaxed_testing_profile_hint=relaxed_testing_profile_hint,
        relaxed_testing_remove_exclude_keywords=relaxed_testing_remove_exclude_keywords,
        relaxed_testing_minimum_relevance=relaxed_testing_minimum_relevance,
        target_seniorities=target_seniorities,
        allow_unknown_seniority=True,
    )


def build_matching_criteria_from_structured_config(
    *,
    structured_matching: StructuredMatchingSource,
    relaxed_matching_for_testing: bool,
    relaxed_testing_profile_hint: str,
    relaxed_testing_remove_exclude_keywords: tuple[str, ...],
    relaxed_testing_minimum_relevance: int,
) -> MatchingCriteria:
    return build_matching_criteria(
        profile_text=structured_matching.profile.summary,
        include_keywords=structured_matching.matching.include_keywords,
        exclude_keywords=structured_matching.matching.exclude_keywords,
        accepted_work_modes=structured_matching.matching.accepted_work_modes,
        minimum_salary_brl=structured_matching.matching.minimum_salary_brl,
        minimum_relevance=structured_matching.matching.minimum_relevance,
        relaxed_matching_for_testing=relaxed_matching_for_testing,
        relaxed_testing_profile_hint=relaxed_testing_profile_hint,
        relaxed_testing_remove_exclude_keywords=relaxed_testing_remove_exclude_keywords,
        relaxed_testing_minimum_relevance=relaxed_testing_minimum_relevance,
        target_seniorities=structured_matching.matching.target_seniorities,
        allow_unknown_seniority=structured_matching.matching.allow_unknown_seniority,
    )
