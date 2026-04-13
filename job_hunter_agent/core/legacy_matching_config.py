from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LegacyMatchingConfig:
    profile_text: str
    include_keywords: tuple[str, ...]
    exclude_keywords: tuple[str, ...]
    accepted_work_modes: tuple[str, ...]
    minimum_salary_brl: int
    minimum_relevance: int


def build_legacy_matching_config_from_settings(settings) -> LegacyMatchingConfig:
    return LegacyMatchingConfig(
        profile_text=settings.profile_text,
        include_keywords=tuple(settings.include_keywords),
        exclude_keywords=tuple(settings.exclude_keywords),
        accepted_work_modes=tuple(settings.accepted_work_modes),
        minimum_salary_brl=settings.minimum_salary_brl,
        minimum_relevance=settings.minimum_relevance,
    )
