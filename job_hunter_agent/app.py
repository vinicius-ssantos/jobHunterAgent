from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timedelta

from job_hunter_agent.applicant import ApplicationPreparationService, ApplicationPreflightService
from job_hunter_agent.collector import (
    BrowserUseSiteCollector,
    HybridJobScorer,
    JobCollectionService,
)
from job_hunter_agent.linkedin import LinkedInDeterministicCollector, OllamaLinkedInFieldRepairer
from job_hunter_agent.linkedin_auth import bootstrap_linkedin_storage_state
from job_hunter_agent.notifier import NullNotifier, TelegramNotifier
from job_hunter_agent.repository import SqliteJobRepository
from job_hunter_agent.settings import load_settings
from job_hunter_agent.runtime import RuntimeGuard


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class JobHunterApplication:
    def __init__(self, *, enable_telegram: bool = True) -> None:
        self.enable_telegram = enable_telegram
        self.settings = load_settings()
        self.repository = SqliteJobRepository(self.settings.database_path)
        self.runtime_guard = RuntimeGuard(
            project_root=self.settings.database_path.resolve().parent,
            browser_use_dir=self.settings.browser_use_config_dir.resolve(),
            lock_path=(self.settings.browser_use_config_dir / "job_hunter_agent.lock").resolve(),
        )
        self.application_preparation = ApplicationPreparationService(self.repository)
        self.application_preflight = ApplicationPreflightService(self.repository)
        self.collector = JobCollectionService(
            settings=self.settings,
            repository=self.repository,
            site_collector=BrowserUseSiteCollector(
                model_name=self.settings.ollama_model,
                base_url=self.settings.ollama_url,
                config_dir=self.settings.browser_use_config_dir,
                persistent_profile_dir=self.settings.linkedin_persistent_profile_dir,
                linkedin_storage_state_path=self.settings.linkedin_storage_state_path,
                headless=self.settings.browser_headless,
                known_job_url_exists=self.repository.job_url_exists,
                linkedin_collector=LinkedInDeterministicCollector(
                    storage_state_path=self.settings.linkedin_storage_state_path,
                    headless=self.settings.browser_headless,
                    known_job_url_exists=self.repository.job_url_exists,
                    field_repairer=(
                        OllamaLinkedInFieldRepairer(
                            model_name=self.settings.ollama_model,
                            base_url=self.settings.ollama_url,
                        )
                        if self.settings.linkedin_field_repair_enabled
                        else None
                    ),
                ),
            ),
            scorer=HybridJobScorer(
                model_name=self.settings.ollama_model,
                base_url=self.settings.ollama_url,
            ),
        )
        self.notifier = (
            TelegramNotifier(
                settings=self.settings,
                repository=self.repository,
                on_approved=self.handle_approved_jobs,
                on_application_preflight=self.handle_application_preflight,
            )
            if enable_telegram
            else NullNotifier()
        )

    async def handle_approved_jobs(self, job_ids: list[int]) -> None:
        drafts = self.application_preparation.create_drafts_for_approved_jobs(
            job_ids,
            notes="rascunho criado apos aprovacao humana",
        )
        if drafts:
            logger.info("Pre-fase de candidatura criou %s rascunho(s) para vagas aprovadas.", len(drafts))

    async def handle_application_preflight(self, application_id: int) -> str:
        result = self.application_preflight.run_for_application(application_id)
        logger.info(
            "Preflight de candidatura concluido. application_id=%s outcome=%s status=%s",
            application_id,
            result.outcome,
            result.application_status,
        )
        return f"Preflight: {result.detail} (status={result.application_status})"

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
            await self.notifier.stop()
            self.runtime_guard.release()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Job Hunter Agent")
    parser.add_argument("--agora", action="store_true", help="Roda um ciclo imediatamente e encerra.")
    parser.add_argument("--sem-telegram", action="store_true", help="Executa sem iniciar o Telegram.")
    parser.add_argument(
        "--ciclos",
        type=int,
        default=None,
        help="Roda um numero finito de ciclos imediatamente, sem usar o agendamento diario.",
    )
    parser.add_argument(
        "--intervalo-ciclos-segundos",
        type=int,
        default=0,
        help="Intervalo em segundos entre ciclos quando usado com --ciclos.",
    )
    parser.add_argument(
        "--bootstrap-linkedin-session",
        action="store_true",
        help="Abre o Chromium para exportar o storage_state autenticado do LinkedIn.",
    )
    args = parser.parse_args()
    if args.ciclos is not None and args.ciclos <= 0:
        parser.error("--ciclos deve ser maior que zero")
    if args.intervalo_ciclos_segundos < 0:
        parser.error("--intervalo-ciclos-segundos nao pode ser negativo")
    if args.agora and args.ciclos is not None:
        parser.error("use --agora ou --ciclos, nao ambos")
    return args


def run() -> None:
    args = parse_args()
    if args.bootstrap_linkedin_session:
        settings = load_settings()
        asyncio.run(bootstrap_linkedin_storage_state(settings))
        return
    asyncio.run(
        JobHunterApplication(enable_telegram=not args.sem_telegram).run(
            run_once=args.agora,
            fixed_cycles=args.ciclos,
            cycle_interval_seconds=args.intervalo_ciclos_segundos,
        )
    )
