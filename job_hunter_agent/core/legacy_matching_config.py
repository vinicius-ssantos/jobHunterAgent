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
    profile_text = str(getattr(settings, "profile_text", "")).strip()
    if not profile_text:
        raise ValueError(
            "Fallback legado exige JOB_HUNTER_PROFILE_TEXT nao vazio ou desabilite JOB_HUNTER_STRUCTURED_MATCHING_FALLBACK_ENABLED."
        )
    include_keywords = tuple(
        token.strip().lower()
        for token in tuple(getattr(settings, "include_keywords", ()))
        if str(token).strip()
    )
    if not include_keywords:
        raise ValueError(
            "Fallback legado exige include_keywords configurado ou desabilite JOB_HUNTER_STRUCTURED_MATCHING_FALLBACK_ENABLED."
        )
    exclude_keywords = tuple(
        token.strip().lower()
        for token in tuple(getattr(settings, "exclude_keywords", ()))
        if str(token).strip()
    )
    accepted_work_modes = tuple(
        token.strip().lower()
        for token in tuple(getattr(settings, "accepted_work_modes", ()))
        if str(token).strip()
    )
    return LegacyMatchingConfig(
        profile_text=profile_text,
        include_keywords=include_keywords,
        exclude_keywords=exclude_keywords,
        accepted_work_modes=accepted_work_modes,
        minimum_salary_brl=settings.minimum_salary_brl,
        minimum_relevance=settings.minimum_relevance,
    )
