from __future__ import annotations

from typing import Callable

from job_hunter_agent.applicant import (
    ApplicationPreparationService,
    ApplicationPreflightService,
    OllamaApplicationSupportAssessor,
)
from job_hunter_agent.application_priority import OllamaApplicationPriorityAssessor
from job_hunter_agent.collector import HybridJobScorer, JobCollectionService
from job_hunter_agent.job_identity import PortalAwareJobIdentityStrategy
from job_hunter_agent.job_requirements import OllamaJobRequirementsExtractor
from job_hunter_agent.linkedin import LinkedInDeterministicCollector, OllamaLinkedInFieldRepairer
from job_hunter_agent.notifier import NullNotifier, TelegramNotifier
from job_hunter_agent.portal_collectors import BrowserUseSiteCollector
from job_hunter_agent.repository import JobRepository, SqliteJobRepository
from job_hunter_agent.review_rationale import OllamaReviewRationaleFormatter
from job_hunter_agent.runtime import RuntimeGuard
from job_hunter_agent.settings import Settings


def create_repository(settings: Settings) -> JobRepository:
    return SqliteJobRepository(
        settings.database_path,
        identity_strategy=PortalAwareJobIdentityStrategy(),
    )


def create_runtime_guard(settings: Settings) -> RuntimeGuard:
    return RuntimeGuard(
        project_root=settings.database_path.resolve().parent,
        browser_use_dir=settings.browser_use_config_dir.resolve(),
        lock_path=(settings.browser_use_config_dir / "job_hunter_agent.lock").resolve(),
    )


def build_known_job_lookup(repository: JobRepository) -> Callable[[str], bool]:
    return lambda url: repository.job_url_exists(url) or repository.seen_job_url_exists(url)


def create_application_support_assessor(settings: Settings) -> OllamaApplicationSupportAssessor | None:
    if not settings.application_support_llm_enabled:
        return None
    return OllamaApplicationSupportAssessor(
        model_name=settings.ollama_model,
        base_url=settings.ollama_url,
    )


def create_job_requirements_extractor(settings: Settings) -> OllamaJobRequirementsExtractor | None:
    if not settings.job_requirements_llm_enabled:
        return None
    return OllamaJobRequirementsExtractor(
        model_name=settings.ollama_model,
        base_url=settings.ollama_url,
    )


def create_application_priority_assessor(settings: Settings) -> OllamaApplicationPriorityAssessor | None:
    if not settings.application_priority_llm_enabled:
        return None
    return OllamaApplicationPriorityAssessor(
        model_name=settings.ollama_model,
        base_url=settings.ollama_url,
    )


def create_application_preparation_service(
    repository: JobRepository,
    settings: Settings,
) -> ApplicationPreparationService:
    return ApplicationPreparationService(
        repository,
        support_assessor=create_application_support_assessor(settings),
        requirements_extractor=create_job_requirements_extractor(settings),
        priority_assessor=create_application_priority_assessor(settings),
    )


def create_application_preflight_service(repository: JobRepository) -> ApplicationPreflightService:
    return ApplicationPreflightService(repository)


def create_collection_service(settings: Settings, repository: JobRepository) -> JobCollectionService:
    known_job_lookup = build_known_job_lookup(repository)
    return JobCollectionService(
        settings=settings,
        repository=repository,
        site_collector=BrowserUseSiteCollector(
            model_name=settings.ollama_model,
            base_url=settings.ollama_url,
            config_dir=settings.browser_use_config_dir,
            persistent_profile_dir=settings.linkedin_persistent_profile_dir,
            linkedin_storage_state_path=settings.linkedin_storage_state_path,
            headless=settings.browser_headless,
            known_job_url_exists=known_job_lookup,
            linkedin_collector=LinkedInDeterministicCollector(
                storage_state_path=settings.linkedin_storage_state_path,
                headless=settings.browser_headless,
                max_pages_per_cycle=settings.linkedin_max_pages_per_cycle,
                known_job_url_exists=known_job_lookup,
                field_repairer=create_linkedin_field_repairer(settings),
            ),
        ),
        scorer=HybridJobScorer(
            model_name=settings.ollama_model,
            base_url=settings.ollama_url,
        ),
    )


def create_linkedin_field_repairer(settings: Settings) -> OllamaLinkedInFieldRepairer | None:
    if not settings.linkedin_field_repair_enabled:
        return None
    return OllamaLinkedInFieldRepairer(
        model_name=settings.ollama_model,
        base_url=settings.ollama_url,
    )


def create_notifier(
    *,
    settings: Settings,
    repository: JobRepository,
    enable_telegram: bool,
    on_approved,
    on_application_preflight,
):
    if not enable_telegram:
        return NullNotifier()
    return TelegramNotifier(
        settings=settings,
        repository=repository,
        on_approved=on_approved,
        on_application_preflight=on_application_preflight,
        review_rationale_formatter=create_review_rationale_formatter(settings),
    )


def create_review_rationale_formatter(settings: Settings) -> OllamaReviewRationaleFormatter | None:
    if not settings.review_rationale_llm_enabled:
        return None
    return OllamaReviewRationaleFormatter(
        model_name=settings.ollama_model,
        base_url=settings.ollama_url,
    )
