from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from job_hunter_agent.application.application_commands import (
    ApplicationDraftCommandService,
    ApplicationTransitionCommandService,
    JobReviewCommandService,
)
from job_hunter_agent.application.auto_easy_apply import (
    AutoEasyApplyService,
    render_auto_easy_apply_report,
)
from job_hunter_agent.application.application_health import (
    build_application_health_report,
    render_application_health_report,
)
from job_hunter_agent.application.application_messages import (
    format_preflight_cli_result,
    format_preflight_dry_run_cli_result,
    format_submit_cli_result,
    format_submit_dry_run_cli_result,
)
from job_hunter_agent.application.application_queries import ApplicationQueryService
from job_hunter_agent.application.application_cli_rendering import render_failure_artifacts
from job_hunter_agent.application.composition import (
    create_application_preflight_service,
    create_application_preparation_service,
    create_application_submission_service,
    create_collection_service,
    create_domain_event_bus,
    create_notifier,
    create_repository,
    create_runtime_guard,
)
from job_hunter_agent.application.runtime_execution import (
    run_application as run_application_runtime,
    run_collection_cycle as run_collection_cycle_runtime,
    run_fixed_cycles as run_fixed_cycles_runtime,
    run_scheduler as run_scheduler_runtime,
    wait_for_review_window as wait_for_review_window_runtime,
)
from job_hunter_agent.application.runtime_handlers import (
    handle_application_preflight as run_application_preflight_handler,
    handle_application_submit as run_application_submit_handler,
    handle_approved_jobs as run_approved_jobs_handler,
)
from job_hunter_agent.llm.candidate_profile_extractor import (
    OllamaCandidateProfileSuggester,
    extract_resume_text,
    merge_candidate_profile_suggestions,
)
from job_hunter_agent.core.settings import load_settings


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def suggest_candidate_profile(
    *,
    resume_path: Path,
    output_path: Path,
    model_name: str,
    base_url: str,
) -> str:
    if not resume_path.exists():
        return f"Curriculo nao encontrado: {resume_path}"
    resume_text = extract_resume_text(resume_path)
    if not resume_text.strip():
        return f"Nao foi possivel extrair texto do curriculo: {resume_path}"
    suggester = OllamaCandidateProfileSuggester(model_name=model_name, base_url=base_url)
    suggestion = suggester.suggest_from_resume_text(resume_text)
    written_path = merge_candidate_profile_suggestions(
        output_path=output_path,
        suggestion=suggestion,
        source_resume=resume_path,
    )
    if not suggestion.experience_years:
        return f"Perfil sugerido sem tecnologias mapeadas: {written_path}"
    mapped = ", ".join(f"{skill}={years}" for skill, years in sorted(suggestion.experience_years.items()))
    return f"Perfil sugerido atualizado: {written_path} | sugestoes={mapped}"


class JobHunterApplication:
    def __init__(self, *, enable_telegram: bool = True) -> None:
        self.enable_telegram = enable_telegram
        self.settings = load_settings()
        self.repository = create_repository(self.settings)
        self.domain_event_bus = create_domain_event_bus(self.settings)
        self._initialize_query_services()
        self._initialize_review_services()
        self._initialize_flow_services()
        self.runtime_guard = create_runtime_guard(self.settings)
        self.collector = create_collection_service(
            settings=self.settings,
            repository=self.repository,
        )
        self.notifier = create_notifier(
            settings=self.settings,
            repository=self.repository,
            enable_telegram=enable_telegram,
            on_approved=self.handle_approved_jobs,
            on_application_preflight=self.handle_application_preflight,
            on_application_submit=self.handle_application_submit,
        )

    def _initialize_query_services(self) -> None:
        self.query = ApplicationQueryService(self.repository, domain_event_bus=getattr(self, "domain_event_bus", None))

    def _initialize_review_services(self) -> None:
        self.application_preparation = create_application_preparation_service(self.repository, self.settings)
        self.job_review_commands = JobReviewCommandService(self.repository, event_bus=self.domain_event_bus)
        self.application_draft_commands = ApplicationDraftCommandService(
            self.repository,
            self.application_preparation,
            event_bus=self.domain_event_bus,
        )
        self.application_transition_commands = ApplicationTransitionCommandService(
            self.repository,
            event_bus=self.domain_event_bus,
        )

    def _initialize_flow_services(self) -> None:
        self.application_preflight = create_application_preflight_service(
            self.repository,
            self.settings,
            event_bus=self.domain_event_bus,
        )
        self.application_submission = create_application_submission_service(
            self.repository,
            self.settings,
            event_bus=self.domain_event_bus,
        )
        self.auto_easy_apply = AutoEasyApplyService(
            repository=self.repository,
            preflight=self.application_preflight,
            submission=self.application_submission,
            transitions=self._application_transition_commands(),
            settings=self.settings,
        )

    async def handle_approved_jobs(self, job_ids: list[int]) -> None:
        await run_approved_jobs_handler(
            self.application_preparation,
            job_ids,
            logger=logger,
        )

    async def handle_application_preflight(self, application_id: int) -> str:
        return await run_application_preflight_handler(
            self.application_preflight,
            application_id,
            logger=logger,
        )

    async def handle_application_submit(self, application_id: int) -> str:
        return await run_application_submit_handler(
            self.application_submission,
            application_id,
            logger=logger,
        )

    def show_application_preflight_dry_run(self, application_id: int) -> str:
        result = self.application_preflight.run_dry_run_for_application(application_id)
        return format_preflight_dry_run_cli_result(
            detail=result.detail,
            application_status=result.application_status,
        )

    def show_application_submit_dry_run(self, application_id: int) -> str:
        result = self.application_submission.run_dry_run_for_application(application_id)
        return format_submit_dry_run_cli_result(
            detail=result.detail,
            application_status=result.application_status,
        )

    def run_auto_easy_apply_once(self) -> str:
        service = getattr(self, "auto_easy_apply", None)
        if service is None:
            self._initialize_flow_services()
            service = self.auto_easy_apply
        return render_auto_easy_apply_report(service.run_once())

    def list_applications(self, *, status: str | None = None) -> str:
        return self._query_service().list_applications(status=status)

    def list_jobs(self, *, status: str | None = None) -> str:
        return self._query_service().list_jobs(status=status)

    def show_job(self, job_id: int) -> str:
        return self._query_service().show_job(job_id)

    def show_status_overview(self) -> str:
        return self._query_service().show_status_overview()

    def show_health_report(self) -> str:
        return render_application_health_report(build_application_health_report(self.settings))

    def review_job(self, job_id: int, action: str) -> str:
        return self._job_review_commands().review_job(job_id, action)

    def create_application_draft_for_job(self, job_id: int) -> str:
        return self._application_draft_commands().create_application_draft_for_job(job_id)

    def show_application_events(self, application_id: int, *, limit: int = 10) -> str:
        return self._query_service().show_application_events(application_id, limit=limit)

    def show_application(self, application_id: int) -> str:
        return self._query_service().show_application(application_id)

    def diagnose_application(self, application_id: int) -> str:
        return self._query_service().diagnose_application(application_id)

    def generate_application_report(
        self,
        application_id: int,
        *,
        output_path: Path | None = None,
        force: bool = False,
    ) -> str:
        return self._query_service().generate_application_report(
            application_id,
            output_path=output_path,
            force=force,
        )

    def transition_application(self, application_id: int, action: str) -> str:
        return self._application_transition_commands().transition_application(application_id, action)

    def authorize_application(self, application_id: int) -> str:
        return self._application_transition_commands().authorize_application(application_id)

    def show_latest_failure_artifacts(self, *, limit: int = 5) -> str:
        artifacts_dir = Path(self.settings.failure_artifacts_dir)
        files = sorted(
            artifacts_dir.glob("*_meta.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return render_failure_artifacts(
            artifacts_dir=artifacts_dir,
            files=files,
            limit=limit,
        )

    async def run_collection_cycle(self) -> bool:
        jobs_sent_for_review = await run_collection_cycle_runtime(
            self.repository,
            self.collector,
            self.notifier,
            logger=logger,
        )
        if getattr(self.settings, "auto_easy_apply_enabled", False):
            auto_apply_report = await asyncio.to_thread(self.run_auto_easy_apply_once)
            logger.info("Execucao auto easy apply apos ciclo:\n%s", auto_apply_report)
        return jobs_sent_for_review

    async def wait_for_review_window(self) -> None:
        await wait_for_review_window_runtime(
            enable_telegram=self.enable_telegram,
            grace_seconds=self.settings.review_polling_grace_seconds,
            logger=logger,
        )

    async def run_scheduler(self) -> None:
        await run_scheduler_runtime(
            collection_time=self.settings.collection_time,
            run_collection_cycle=self.run_collection_cycle,
            logger=logger,
        )

    async def run_fixed_cycles(self, cycles: int, interval_seconds: int = 0) -> None:
        await run_fixed_cycles_runtime(
            cycles=cycles,
            interval_seconds=interval_seconds,
            run_collection_cycle=self.run_collection_cycle,
            wait_for_review_window=self.wait_for_review_window,
            adaptive_backoff_enabled=getattr(self.settings, "adaptive_polling_backoff_enabled", True),
            empty_cycles_before_backoff=getattr(self.settings, "adaptive_polling_empty_cycles_before_backoff", 2),
            backoff_multiplier=getattr(self.settings, "adaptive_polling_backoff_multiplier", 2.0),
            backoff_max_interval_seconds=getattr(self.settings, "adaptive_polling_max_interval_seconds", 900),
            logger=logger,
        )

    async def run(self, run_once: bool, fixed_cycles: int | None = None, cycle_interval_seconds: int = 0) -> None:
        await run_application_runtime(
            run_once=run_once,
            fixed_cycles=fixed_cycles,
            cycle_interval_seconds=cycle_interval_seconds,
            runtime_guard=self.runtime_guard,
            repository=self.repository,
            notifier=self.notifier,
            build_execution_summary=self.build_execution_summary,
            run_collection_cycle=self.run_collection_cycle,
            wait_for_review_window=self.wait_for_review_window,
            run_fixed_cycles_callback=self.run_fixed_cycles,
            run_scheduler_callback=self.run_scheduler,
            logger=logger,
        )

    def build_execution_summary(self, since: str) -> str:
        return self._query_service().build_execution_summary(since)

    def _query_service(self) -> ApplicationQueryService:
        query = getattr(self, "query", None)
        if query is None:
            query = ApplicationQueryService(
                self.repository,
                domain_event_bus=getattr(self, "domain_event_bus", None),
            )
            self.query = query
        return query

    def _job_review_commands(self) -> JobReviewCommandService:
        service = getattr(self, "job_review_commands", None)
        if service is None:
            service = JobReviewCommandService(self.repository, event_bus=getattr(self, "domain_event_bus", None))
            self.job_review_commands = service
        return service

    def _application_draft_commands(self) -> ApplicationDraftCommandService:
        service = getattr(self, "application_draft_commands", None)
        if service is None:
            service = ApplicationDraftCommandService(
                self.repository,
                self.application_preparation,
                event_bus=getattr(self, "domain_event_bus", None),
            )
            self.application_draft_commands = service
        return service

    def _application_transition_commands(self) -> ApplicationTransitionCommandService:
        service = getattr(self, "application_transition_commands", None)
        if service is None:
            service = ApplicationTransitionCommandService(
                self.repository,
                event_bus=getattr(self, "domain_event_bus", None),
            )
            self.application_transition_commands = service
        return service


def run() -> None:
    from job_hunter_agent.application.application_cli import run as run_cli

    run_cli()


def parse_args():
    from job_hunter_agent.application.application_cli import parse_args as parse_cli_args

    return parse_cli_args()
