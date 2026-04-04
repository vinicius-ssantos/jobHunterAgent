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

    @field_validator("sites")
    @classmethod
    def validate_sites(cls, value: tuple[SiteConfig, ...]) -> tuple[SiteConfig, ...]:
        if not any(site.enabled for site in value):
            raise ValueError("Ative pelo menos um site.")
        return value


def load_settings() -> Settings:
    return Settings()
