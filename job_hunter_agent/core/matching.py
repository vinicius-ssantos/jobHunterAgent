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
