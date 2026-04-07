from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatchingCriteria:
    profile_text: str
    include_keywords: tuple[str, ...]
    exclude_keywords: tuple[str, ...]
    accepted_work_modes: tuple[str, ...]
    minimum_salary_brl: int
    minimum_relevance: int


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
