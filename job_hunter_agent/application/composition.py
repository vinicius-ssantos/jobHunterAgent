from __future__ import annotations

from typing import Callable

from job_hunter_agent.application.application_preflight import ApplicationPreflightService
from job_hunter_agent.application.application_preparation import ApplicationPreparationService
from job_hunter_agent.application.application_submission import ApplicationSubmissionService
from job_hunter_agent.application.application_support import OllamaApplicationSupportAssessor
from job_hunter_agent.application.application_readiness import ApplicationReadinessCheckService
from job_hunter_agent.llm.application_priority import OllamaApplicationPriorityAssessor
from job_hunter_agent.collectors.collector import HybridJobScorer, JobCollectionService
from job_hunter_agent.core.candidate_profile import load_candidate_profile
from job_hunter_agent.core.job_identity import PortalAwareJobIdentityStrategy
from job_hunter_agent.core.matching import build_matching_criteria
from job_hunter_agent.llm.job_requirements import OllamaJobRequirementsExtractor
from job_hunter_agent.collectors.linkedin_application import LinkedInApplicationFlowInspector
from job_hunter_agent.collectors.linkedin_modal_llm import (
    OllamaLinkedInModalInterpreter,
    deterministic_interpret_linkedin_modal,
    format_linkedin_modal_interpretation,
    validate_linkedin_modal_interpretation,
)
from job_hunter_agent.collectors.linkedin import LinkedInDeterministicCollector, OllamaLinkedInFieldRepairer
from job_hunter_agent.infrastructure.notifier import NullNotifier, TelegramNotifier
from job_hunter_agent.collectors.portal_collectors import BrowserUseSiteCollector
from job_hunter_agent.infrastructure.repository import JobRepository, SqliteJobRepository
from job_hunter_agent.llm.review_rationale import OllamaReviewRationaleFormatter
from job_hunter_agent.core.runtime import RuntimeGuard
from job_hunter_agent.core.settings import Settings
from job_hunter_agent.collectors.linkedin_application_artifacts import LinkedInFailureArtifactCapture


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


def create_application_preflight_service(repository: JobRepository, settings: Settings) -> ApplicationPreflightService:
    return ApplicationPreflightService(
        repository,
        flow_inspector=create_linkedin_application_flow_inspector(
            settings,
            mode="preflight",
        ),
        readiness_checker=ApplicationReadinessCheckService(
            linkedin_storage_state_path=settings.linkedin_storage_state_path,
            resume_path=settings.resume_path,
            contact_email=settings.application_contact_email,
            phone=settings.application_phone,
            phone_country_code=settings.application_phone_country_code,
        ),
    )


def create_application_submission_service(repository: JobRepository, settings: Settings) -> ApplicationSubmissionService:
    return ApplicationSubmissionService(
        repository,
        applicant=create_linkedin_application_flow_inspector(
            settings,
            mode="submit",
        ),
        readiness_checker=ApplicationReadinessCheckService(
            linkedin_storage_state_path=settings.linkedin_storage_state_path,
            resume_path=settings.resume_path,
            contact_email=settings.application_contact_email,
            phone=settings.application_phone,
            phone_country_code=settings.application_phone_country_code,
        ),
    )


def create_linkedin_modal_interpretation_formatter(settings: Settings):
    interpreter = create_linkedin_modal_interpreter(settings)
    if interpreter is None:
        return None

    def _format(state) -> str:
        chosen = interpreter(state)
        return format_linkedin_modal_interpretation(chosen)

    return _format


def create_linkedin_modal_interpreter(settings: Settings):
    if not settings.linkedin_modal_llm_enabled:
        return None
    llm_interpreter = OllamaLinkedInModalInterpreter(
        model_name=settings.ollama_model,
        base_url=settings.ollama_url,
    )

    def _interpret(state):
        interpreted = llm_interpreter.interpret(state)
        guarded = validate_linkedin_modal_interpretation(state, interpreted)
        fallback = deterministic_interpret_linkedin_modal(state)
        return guarded if guarded.confidence >= fallback.confidence else fallback

    return _interpret


def create_collection_service(settings: Settings, repository: JobRepository) -> JobCollectionService:
    known_job_lookup = build_known_job_lookup(repository)
    return JobCollectionService(
        settings=settings,
        matching_criteria=build_matching_criteria(
            profile_text=settings.profile_text,
            include_keywords=settings.include_keywords,
            exclude_keywords=settings.exclude_keywords,
            accepted_work_modes=settings.accepted_work_modes,
            minimum_salary_brl=settings.minimum_salary_brl,
            minimum_relevance=settings.minimum_relevance,
            relaxed_matching_for_testing=settings.relaxed_matching_for_testing,
            relaxed_testing_profile_hint=settings.relaxed_testing_profile_hint,
            relaxed_testing_remove_exclude_keywords=settings.relaxed_testing_remove_exclude_keywords,
            relaxed_testing_minimum_relevance=settings.relaxed_testing_minimum_relevance,
        ),
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
                max_page_depth=settings.linkedin_max_page_depth,
                scroll_stabilization_passes=settings.linkedin_scroll_stabilization_passes,
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


def create_linkedin_application_flow_inspector(
    settings: Settings,
    *,
    mode: str,
) -> LinkedInApplicationFlowInspector:
    shared_kwargs = {
        "storage_state_path": settings.linkedin_storage_state_path,
        "headless": settings.browser_headless,
        "resume_path": settings.resume_path,
        "contact_email": settings.application_contact_email,
        "phone": settings.application_phone,
        "phone_country_code": settings.application_phone_country_code,
        "candidate_profile": load_candidate_profile(settings.candidate_profile_path),
        "candidate_profile_path": settings.candidate_profile_path,
        "save_failure_artifacts": settings.save_failure_artifacts,
        "failure_artifacts_dir": settings.failure_artifacts_dir,
        "artifact_capture": LinkedInFailureArtifactCapture(
            enabled=settings.save_failure_artifacts,
            artifacts_dir=settings.failure_artifacts_dir,
        ),
    }
    if mode == "preflight":
        return LinkedInApplicationFlowInspector(
            **shared_kwargs,
            modal_interpretation_formatter=create_linkedin_modal_interpretation_formatter(settings),
        )
    if mode == "submit":
        return LinkedInApplicationFlowInspector(
            **shared_kwargs,
            modal_interpreter=create_linkedin_modal_interpreter(settings),
        )
    raise ValueError(f"modo de inspector do LinkedIn nao suportado: {mode}")


def create_notifier(
    *,
    settings: Settings,
    repository: JobRepository,
    enable_telegram: bool,
    on_approved,
    on_application_preflight,
    on_application_submit,
):
    if not enable_telegram:
        return NullNotifier()
    return TelegramNotifier(
        settings=settings,
        repository=repository,
        on_approved=on_approved,
        on_application_preflight=on_application_preflight,
        on_application_submit=on_application_submit,
        review_rationale_formatter=create_review_rationale_formatter(settings),
    )


def create_review_rationale_formatter(settings: Settings) -> OllamaReviewRationaleFormatter | None:
    if not settings.review_rationale_llm_enabled:
        return None
    return OllamaReviewRationaleFormatter(
        model_name=settings.ollama_model,
        base_url=settings.ollama_url,
    )
