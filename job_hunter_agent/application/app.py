from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from job_hunter_agent.application.application_commands import (
    ApplicationDraftCommandService,
    ApplicationTransitionCommandService,
    JobReviewCommandService,
)
from job_hunter_agent.application.application_messages import (
    format_preflight_cli_result,
    format_submit_cli_result,
)
from job_hunter_agent.application.application_queries import ApplicationQueryService
from job_hunter_agent.application.application_cli_rendering import render_failure_artifacts
from job_hunter_agent.collectors.collector import JobCollectionService
from job_hunter_agent.application.composition import (
    create_application_preflight_service,
    create_application_preparation_service,
    create_application_submission_service,
    create_collection_service,
    create_notifier,
    create_repository,
    create_runtime_guard,
)
from job_hunter_agent.llm.candidate_profile_extractor import (
    OllamaCandidateProfileSuggester,
    extract_resume_text,
    merge_candidate_profile_suggestions,
)
from job_hunter_agent.infrastructure.notifier import NullNotifier, TelegramNotifier
from job_hunter_agent.infrastructure.repository import JobRepository
from job_hunter_agent.core.settings import load_settings
from job_hunter_agent.core.runtime import RuntimeGuard


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
        self.runtime_guard = create_runtime_guard(self.settings)
        self.application_preparation = create_application_preparation_service(self.repository, self.settings)
        self.application_preflight = create_application_preflight_service(self.repository, self.settings)
        self.application_submission = create_application_submission_service(self.repository, self.settings)
        self.query = ApplicationQueryService(self.repository)
        self.job_review_commands = JobReviewCommandService(self.repository)
        self.application_draft_commands = ApplicationDraftCommandService(
            self.repository,
            self.application_preparation,
        )
        self.application_transition_commands = ApplicationTransitionCommandService(self.repository)
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

    async def handle_approved_jobs(self, job_ids: list[int]) -> None:
        drafts = self.application_preparation.create_drafts_for_approved_jobs(
            job_ids,
            notes="rascunho criado apos aprovacao humana",
        )
        if drafts:
            logger.info("Pre-fase de candidatura criou %s rascunho(s) para vagas aprovadas.", len(drafts))

    async def handle_application_preflight(self, application_id: int) -> str:
        result = await asyncio.to_thread(self.application_preflight.run_for_application, application_id)
        logger.info(
            "Preflight de candidatura concluido. application_id=%s outcome=%s status=%s",
            application_id,
            result.outcome,
            result.application_status,
        )
        return format_preflight_cli_result(
            detail=result.detail,
            application_status=result.application_status,
        )

    async def handle_application_submit(self, application_id: int) -> str:
        result = await asyncio.to_thread(self.application_submission.run_for_application, application_id)
        logger.info(
            "Submissao de candidatura concluida. application_id=%s outcome=%s status=%s",
            application_id,
            result.outcome,
            result.application_status,
        )
        return format_submit_cli_result(
            detail=result.detail,
            application_status=result.application_status,
        )

    def list_applications(self, *, status: str | None = None) -> str:
        return self._query_service().list_applications(status=status)

    def list_jobs(self, *, status: str | None = None) -> str:
        return self._query_service().list_jobs(status=status)

    def show_job(self, job_id: int) -> str:
        return self._query_service().show_job(job_id)

    def show_status_overview(self) -> str:
        return self._query_service().show_status_overview()

    def review_job(self, job_id: int, action: str) -> str:
        return self._job_review_commands().review_job(job_id, action)

    def create_application_draft_for_job(self, job_id: int) -> str:
        return self._application_draft_commands().create_application_draft_for_job(job_id)

    def show_application_events(self, application_id: int, *, limit: int = 10) -> str:
        return self._query_service().show_application_events(application_id, limit=limit)

    def show_application(self, application_id: int) -> str:
        return self._query_service().show_application(application_id)

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
        run = self.repository.start_collection_run()
        logger.info("Ciclo de coleta iniciado. run_id=%s", run.id)
        try:
            report = await self.collector.collect_new_jobs_report()
            self.repository.finish_collection_run(
                run.id,
                status="success",
                jobs_seen=report.jobs_seen,
                jobs_saved=report.jobs_saved,
                errors=report.errors,
            )
        except Exception as exc:
            self.repository.finish_collection_run(
                run.id,
                status="error",
                jobs_seen=0,
                jobs_saved=0,
                errors=1,
            )
            logger.exception("Falha no ciclo de coleta.")
            await self.notifier.send_text(f"Falha no ciclo de coleta: {exc}")
            return False

        jobs = list(report.jobs)
        if not jobs:
            await self.notifier.send_text("Nenhuma vaga nova passou na triagem de hoje.")
            return False
        await self.notifier.notify_jobs_for_review(jobs)
        return True

    async def wait_for_review_window(self) -> None:
        if not self.enable_telegram:
            return
        grace_seconds = self.settings.review_polling_grace_seconds
        if grace_seconds <= 0:
            return
        logger.info("Aguardando callbacks do Telegram por %ss antes de encerrar.", grace_seconds)
        await asyncio.sleep(grace_seconds)

    async def run_scheduler(self) -> None:
        hour_text, minute_text = self.settings.collection_time.split(":")
        target_hour = int(hour_text)
        target_minute = int(minute_text)

        while True:
            now = datetime.now()
            run_at = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            if run_at <= now:
                run_at += timedelta(days=1)
            delay_seconds = max(1, int((run_at - now).total_seconds()))
            logger.info("Proxima coleta agendada para %s", run_at.isoformat(timespec="minutes"))
            await asyncio.sleep(delay_seconds)
            await self.run_collection_cycle()

    async def run_fixed_cycles(self, cycles: int, interval_seconds: int = 0) -> None:
        for cycle_number in range(1, cycles + 1):
            logger.info("Executando ciclo controlado %s/%s.", cycle_number, cycles)
            jobs_sent_for_review = await self.run_collection_cycle()
            if jobs_sent_for_review:
                await self.wait_for_review_window()
            if cycle_number < cycles and interval_seconds > 0:
                logger.info("Aguardando %ss antes do proximo ciclo controlado.", interval_seconds)
                await asyncio.sleep(interval_seconds)

    async def run(self, run_once: bool, fixed_cycles: int | None = None, cycle_interval_seconds: int = 0) -> None:
        execution_started_at = datetime.now().isoformat(timespec="seconds")
        terminated_processes = self.runtime_guard.prepare_for_startup()
        interrupted_runs = self.repository.interrupt_running_collection_runs()
        if terminated_processes:
            logger.info("Startup limpou processos antigos do projeto: %s", terminated_processes)
        if interrupted_runs:
            logger.info("Startup marcou runs presos como interrompidos: %s", interrupted_runs)
        await self.notifier.start()
        try:
            if run_once:
                jobs_sent_for_review = await self.run_collection_cycle()
                if jobs_sent_for_review:
                    await self.wait_for_review_window()
                return
            if fixed_cycles is not None:
                await self.run_fixed_cycles(fixed_cycles, interval_seconds=cycle_interval_seconds)
                return
            await self.run_scheduler()
        finally:
            logger.info("Resumo final da execucao:\n%s", self.build_execution_summary(execution_started_at))
            await self.notifier.stop()
            self.runtime_guard.release()

    def build_execution_summary(self, since: str) -> str:
        return self._query_service().build_execution_summary(since)

    def _query_service(self) -> ApplicationQueryService:
        query = getattr(self, "query", None)
        if query is None:
            query = ApplicationQueryService(self.repository)
            self.query = query
        return query

    def _job_review_commands(self) -> JobReviewCommandService:
        service = getattr(self, "job_review_commands", None)
        if service is None:
            service = JobReviewCommandService(self.repository)
            self.job_review_commands = service
        return service

    def _application_draft_commands(self) -> ApplicationDraftCommandService:
        service = getattr(self, "application_draft_commands", None)
        if service is None:
            service = ApplicationDraftCommandService(self.repository, self.application_preparation)
            self.application_draft_commands = service
        return service

    def _application_transition_commands(self) -> ApplicationTransitionCommandService:
        service = getattr(self, "application_transition_commands", None)
        if service is None:
            service = ApplicationTransitionCommandService(self.repository)
            self.application_transition_commands = service
        return service

def run() -> None:
    from job_hunter_agent.application.application_cli import run as run_cli

    run_cli()


def parse_args():
    from job_hunter_agent.application.application_cli import parse_args as parse_cli_args

    return parse_cli_args()
