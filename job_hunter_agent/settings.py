from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from job_hunter_agent.domain import SiteConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JOB_HUNTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    user_name: str = "Seu Nome"
    profile_text: str = (
        "Engenheiro de Software Senior com experiencia em Java, Kotlin, Spring Boot, "
        "PostgreSQL, Docker e cloud."
    )
    resume_path: Path = Path("./curriculo.pdf")
    database_path: Path = Path("./jobs.db")
    browser_use_config_dir: Path = Path("./.browseruse")
    linkedin_persistent_profile_dir: Path = Path("./.browseruse/profiles/linkedin-bootstrap")
    linkedin_storage_state_path: Path = Path("./.browseruse/linkedin-storage-state.json")
    browser_headless: bool = False
    linkedin_max_pages_per_cycle: int = 2

    include_keywords: tuple[str, ...] = (
        "java",
        "kotlin",
        "spring",
        "backend",
        "engenheiro de software",
        "software engineer",
        "desenvolvedor backend",
    )
    exclude_keywords: tuple[str, ...] = (
        "estagio",
        "junior",
        "trainee",
        ".net",
        "c#",
        "php",
        "ruby",
    )
    accepted_work_modes: tuple[str, ...] = ("remoto", "hibrido", "hybrid")
    minimum_salary_brl: int = 10000
    minimum_relevance: int = 6
    relaxed_matching_for_testing: bool = False
    relaxed_testing_profile_hint: str = (
        "Para testes controlados de parsing, considere tambem vagas junior e pleno como aceitaveis."
    )
    relaxed_testing_remove_exclude_keywords: tuple[str, ...] = ("junior",)
    relaxed_testing_minimum_relevance: int = 4
    linkedin_field_repair_enabled: bool = True
    application_support_llm_enabled: bool = True
    job_requirements_llm_enabled: bool = True
    review_rationale_llm_enabled: bool = True
    max_jobs_per_site: int = 20
    portal_collection_timeout_seconds: int = 180
    review_polling_grace_seconds: int = 120
    collection_time: str = "08:00"

    telegram_token: str = "SEU_TOKEN_AQUI"
    telegram_chat_id: str = "SEU_CHAT_ID_AQUI"

    ollama_model: str = "qwen2.5:7b"
    ollama_url: str = "http://localhost:11434"

    sites: tuple[SiteConfig, ...] = Field(
        default_factory=lambda: (
            SiteConfig(
                name="LinkedIn",
                search_url="https://www.linkedin.com/jobs/search/?keywords=engenheiro+software+kotlin&location=Brasil",
            ),
        )
    )

    @field_validator("telegram_token")
    @classmethod
    def validate_telegram_token(cls, value: str) -> str:
        if not value or value == "SEU_TOKEN_AQUI":
            raise ValueError("Preencha JOB_HUNTER_TELEGRAM_TOKEN.")
        return value

    @field_validator("telegram_chat_id")
    @classmethod
    def validate_telegram_chat_id(cls, value: str) -> str:
        if not value or value == "SEU_CHAT_ID_AQUI":
            raise ValueError("Preencha JOB_HUNTER_TELEGRAM_CHAT_ID.")
        return value

    @field_validator("profile_text")
    @classmethod
    def validate_profile_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Preencha JOB_HUNTER_PROFILE_TEXT.")
        return value

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

    @field_validator("sites")
    @classmethod
    def validate_sites(cls, value: tuple[SiteConfig, ...]) -> tuple[SiteConfig, ...]:
        if not any(site.enabled for site in value):
            raise ValueError("Ative pelo menos um site.")
        return value

    @property
    def scoring_profile_text(self) -> str:
        if not self.relaxed_matching_for_testing:
            return self.profile_text
        return f"{self.profile_text} {self.relaxed_testing_profile_hint}".strip()

    @property
    def scoring_exclude_keywords(self) -> tuple[str, ...]:
        if not self.relaxed_matching_for_testing:
            return self.exclude_keywords
        blocked = {keyword.lower() for keyword in self.relaxed_testing_remove_exclude_keywords}
        return tuple(keyword for keyword in self.exclude_keywords if keyword.lower() not in blocked)

    @property
    def scoring_minimum_relevance(self) -> int:
        if not self.relaxed_matching_for_testing:
            return self.minimum_relevance
        return self.relaxed_testing_minimum_relevance


def load_settings() -> Settings:
    return Settings()
