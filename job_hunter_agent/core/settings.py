from __future__ import annotations

from pathlib import Path
import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from job_hunter_agent.core.domain import SiteConfig
from job_hunter_agent.core.legacy_matching_config import (
    LegacyMatchingConfig,
    build_legacy_matching_config_from_settings,
)
from job_hunter_agent.core.skill_taxonomy import set_runtime_skill_taxonomy_path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JOB_HUNTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Identidade e runtime principal
    user_name: str = "Seu Nome"
    application_contact_email: str = ""
    application_phone: str = ""
    application_phone_country_code: str = ""
    resume_path: Path = Path("./curriculo.pdf")
    candidate_profile_path: Path = Path("./candidate_profile.json")
    structured_matching_config_path: Path = Path("./job_target.json")
    skill_taxonomy_path: Path = Path("./skill_taxonomy.json")
    structured_matching_fallback_enabled: bool = False
    database_path: Path = Path("./jobs.db")
    browser_use_config_dir: Path = Path("./.browseruse")
    linkedin_persistent_profile_dir: Path = Path("./.browseruse/profiles/linkedin-bootstrap")
    linkedin_storage_state_path: Path = Path("./.browseruse/linkedin-storage-state.json")
    browser_headless: bool = False
    linkedin_max_pages_per_cycle: int = 2
    linkedin_max_page_depth: int = 6
    linkedin_scroll_stabilization_passes: int = 3
    save_failure_artifacts: bool = False
    failure_artifacts_dir: Path = Path("./.artifacts/linkedin_failures")
    max_jobs_per_site: int = 20
    portal_collection_timeout_seconds: int = 180
    review_polling_grace_seconds: int = 120
    collection_time: str = "08:00"

    telegram_token: str = "SEU_TOKEN_AQUI"
    telegram_chat_id: str = "SEU_CHAT_ID_AQUI"

    ollama_model: str = "qwen2.5:7b"
    ollama_url: str = "http://localhost:11434"

    # Matching legado de compatibilidade
    profile_text: str = ""
    include_keywords: tuple[str, ...] = ()
    exclude_keywords: tuple[str, ...] = ()
    accepted_work_modes: tuple[str, ...] = ()
    minimum_salary_brl: int = 0
    minimum_relevance: int = 6

    # Toggles operacionais de teste
    relaxed_matching_for_testing: bool = False
    relaxed_testing_profile_hint: str = (
        "Para testes controlados de parsing, considere tambem vagas junior e pleno como aceitaveis."
    )
    relaxed_testing_remove_exclude_keywords: tuple[str, ...] = ("junior",)
    relaxed_testing_minimum_relevance: int = 4

    # Toggles assistivos locais
    linkedin_field_repair_enabled: bool = True
    linkedin_modal_llm_enabled: bool = False
    application_support_llm_enabled: bool = True
    job_requirements_llm_enabled: bool = True
    review_rationale_llm_enabled: bool = True
    application_priority_llm_enabled: bool = True
    priority_high_min_relevance: int = 8
    priority_medium_min_relevance: int = 6
    priority_preferred_work_modes: tuple[str, ...] = ("remoto", "hibrido", "hybrid", "remote")

    sites: tuple[SiteConfig, ...] = Field(
        default_factory=lambda: (
            SiteConfig(
                name="LinkedIn",
                search_url="https://www.linkedin.com/jobs/search/",
            ),
        )
    )

    def build_legacy_matching_config(self) -> LegacyMatchingConfig:
        return build_legacy_matching_config_from_settings(self)

    @field_validator("profile_text")
    @classmethod
    def validate_profile_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("application_contact_email")
    @classmethod
    def validate_application_contact_email(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return normalized
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalized):
            raise ValueError(
                "JOB_HUNTER_APPLICATION_CONTACT_EMAIL deve conter um email valido."
            )
        return normalized

    @field_validator("application_phone")
    @classmethod
    def validate_application_phone(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return normalized
        digits = "".join(char for char in normalized if char.isdigit())
        if len(digits) < 8:
            raise ValueError(
                "JOB_HUNTER_APPLICATION_PHONE deve conter ao menos 8 digitos."
            )
        return normalized

    @field_validator("application_phone_country_code")
    @classmethod
    def validate_application_phone_country_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return normalized
        digits = "".join(char for char in normalized if char.isdigit())
        if not digits:
            raise ValueError(
                "JOB_HUNTER_APPLICATION_PHONE_COUNTRY_CODE deve conter um codigo com digitos."
            )
        return normalized

    @field_validator(
        "resume_path",
        "linkedin_storage_state_path",
        "structured_matching_config_path",
        "skill_taxonomy_path",
    )
    @classmethod
    def validate_runtime_paths(cls, value: Path, info) -> Path:
        path = Path(value)
        if path.exists() and path.is_dir():
            raise ValueError(f"{info.field_name} deve apontar para um arquivo, nao um diretorio.")
        return path

    @field_validator("collection_time")
    @classmethod
    def validate_collection_time(cls, value: str) -> str:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("JOB_HUNTER_COLLECTION_TIME deve estar no formato HH:MM.")
        hour, minute = parts
        if not (hour.isdigit() and minute.isdigit()):
            raise ValueError("JOB_HUNTER_COLLECTION_TIME deve conter apenas numeros.")
        if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
            raise ValueError("JOB_HUNTER_COLLECTION_TIME esta fora do intervalo valido.")
        return value

    @field_validator("linkedin_max_pages_per_cycle")
    @classmethod
    def validate_linkedin_max_pages_per_cycle(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("JOB_HUNTER_LINKEDIN_MAX_PAGES_PER_CYCLE deve ser maior que zero.")
        return value

    @field_validator("linkedin_max_page_depth")
    @classmethod
    def validate_linkedin_max_page_depth(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("JOB_HUNTER_LINKEDIN_MAX_PAGE_DEPTH deve ser maior que zero.")
        return value

    @field_validator("linkedin_scroll_stabilization_passes")
    @classmethod
    def validate_linkedin_scroll_stabilization_passes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("JOB_HUNTER_LINKEDIN_SCROLL_STABILIZATION_PASSES deve ser maior que zero.")
        return value

    @field_validator("priority_high_min_relevance")
    @classmethod
    def validate_priority_high_min_relevance(cls, value: int) -> int:
        if not (1 <= value <= 10):
            raise ValueError("JOB_HUNTER_PRIORITY_HIGH_MIN_RELEVANCE deve estar entre 1 e 10.")
        return value

    @field_validator("priority_medium_min_relevance")
    @classmethod
    def validate_priority_medium_min_relevance(cls, value: int, info) -> int:
        high = info.data.get("priority_high_min_relevance")
        if not (1 <= value <= 10):
            raise ValueError("JOB_HUNTER_PRIORITY_MEDIUM_MIN_RELEVANCE deve estar entre 1 e 10.")
        if high is not None and value > high:
            raise ValueError(
                "JOB_HUNTER_PRIORITY_MEDIUM_MIN_RELEVANCE nao pode ser maior que JOB_HUNTER_PRIORITY_HIGH_MIN_RELEVANCE."
            )
        return value

    @field_validator("sites")
    @classmethod
    def validate_sites(cls, value: tuple[SiteConfig, ...]) -> tuple[SiteConfig, ...]:
        if not any(site.enabled for site in value):
            raise ValueError("Ative pelo menos um site.")
        return value


def load_settings() -> Settings:
    settings = Settings()
    set_runtime_skill_taxonomy_path(settings.skill_taxonomy_path)
    return settings
