from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from job_hunter_agent.core.domain import VALID_APPLICATION_STATUSES, VALID_STATUSES
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
from job_hunter_agent.application.review_workflow import resolve_application_action
from job_hunter_agent.application.review_workflow import resolve_review_action
from job_hunter_agent.collectors.linkedin_auth import bootstrap_linkedin_storage_state
from job_hunter_agent.infrastructure.notifier import NullNotifier, TelegramNotifier
from job_hunter_agent.infrastructure.repository import JobRepository
from job_hunter_agent.core.settings import load_settings
from job_hunter_agent.core.runtime import RuntimeGuard


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
APPLICATION_STATUS_ORDER = (
    "draft",
    "ready_for_review",
    "confirmed",
    "authorized_submit",
    "submitted",
    "error_submit",
    "cancelled",
)
APPLICATION_STATUS_ALIASES = {
    "all": None,
    "ready": "authorized_submit",
    "review": "ready_for_review",
    "error": "error_submit",
}
JOB_STATUS_ORDER = ("collected", "approved", "rejected", "error_collect")
JOB_STATUS_ALIASES = {
    "all": None,
    "pending": "collected",
    "review": "collected",
    "approved_only": "approved",
}


class JobHunterApplication:
    def __init__(self, *, enable_telegram: bool = True) -> None:
        self.enable_telegram = enable_telegram
        self.settings = load_settings()
        self.repository = create_repository(self.settings)
        self.runtime_guard = create_runtime_guard(self.settings)
        self.application_preparation = create_application_preparation_service(self.repository, self.settings)
        self.application_preflight = create_application_preflight_service(self.repository, self.settings)
        self.application_submission = create_application_submission_service(self.repository, self.settings)
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
        return f"Preflight: {result.detail} (status={result.application_status})"

    async def handle_application_submit(self, application_id: int) -> str:
        result = await asyncio.to_thread(self.application_submission.run_for_application, application_id)
        logger.info(
            "Submissao de candidatura concluida. application_id=%s outcome=%s status=%s",
            application_id,
            result.outcome,
            result.application_status,
        )
        return f"Submissao: {result.detail} (status={result.application_status})"

    def list_applications(self, *, status: str | None = None) -> str:
        requested_statuses = (
            (status,)
            if status is not None
            else tuple(current for current in APPLICATION_STATUS_ORDER if current in VALID_APPLICATION_STATUSES)
        )
        lines: list[str] = []
        total = 0
        for current_status in requested_statuses:
            applications = self.repository.list_applications_by_status(current_status)
            for application in applications:
                job = self.repository.get_job(application.job_id)
                job_label = (
                    f"{job.title} | {job.company}"
                    if job is not None
                    else f"job_id={application.job_id}"
                )
                lines.append(
                    f"{application.id}: {application.status} | {job_label} | suporte={application.support_level}"
                )
                total += 1
        if not lines:
            filter_text = status if status is not None else "todos"
            return f"Nenhuma candidatura encontrada para status={filter_text}."
        return "\n".join([f"Candidaturas listadas: {total}"] + lines)

    def list_jobs(self, *, status: str | None = None) -> str:
        requested_statuses = (
            (status,)
            if status is not None
            else tuple(current for current in JOB_STATUS_ORDER if current in VALID_STATUSES)
        )
        lines: list[str] = []
        total = 0
        for current_status in requested_statuses:
            jobs = self.repository.list_jobs_by_status(current_status)
            for job in jobs:
                lines.append(
                    f"{job.id}: {job.status} | {job.title} | {job.company} | "
                    f"relevancia={job.relevance} | modalidade={job.work_mode}"
                )
                total += 1
        if not lines:
            filter_text = status if status is not None else "todos"
            return f"Nenhuma vaga encontrada para status={filter_text}."
        return "\n".join([f"Vagas listadas: {total}"] + lines)

    def show_job(self, job_id: int) -> str:
        job = self.repository.get_job(job_id)
        if job is None:
            return f"Vaga nao encontrada: id={job_id}"
        application = self.repository.get_application_by_job(job_id)
        lines = [
            f"id={job.id}",
            f"status={job.status}",
            f"titulo={job.title}",
            f"empresa={job.company}",
            f"local={job.location}",
            f"modalidade={job.work_mode}",
            f"salario={job.salary_text}",
            f"relevancia={job.relevance}",
            f"fonte={job.source_site}",
            f"url={job.url}",
            f"rationale={job.rationale}",
            f"summary={job.summary}",
            f"application_id={application.id if application is not None else '-'}",
            f"application_status={application.status if application is not None else '-'}",
        ]
        events = self.repository.list_job_events(job_id, limit=5)
        if events:
            lines.append("eventos_recentes:")
            for event in events:
                lines.append(
                    f"- {event.created_at or '-'} | {event.event_type} | "
                    f"{event.from_status or '-'} -> {event.to_status or '-'} | "
                    f"{event.detail or '-'}"
                )
        return "\n".join(lines)

    def show_status_overview(self) -> str:
        job_summary = self.repository.summary()
        application_summary = self.repository.application_summary()
        lines = [
            "Resumo operacional:",
            "vagas:",
            f"- total={job_summary['total']}",
            f"- collected={job_summary['collected']}",
            f"- approved={job_summary['approved']}",
            f"- rejected={job_summary['rejected']}",
            f"- error_collect={job_summary['error_collect']}",
            "candidaturas:",
            f"- total={application_summary['total']}",
            f"- draft={application_summary['draft']}",
            f"- ready_for_review={application_summary['ready_for_review']}",
            f"- confirmed={application_summary['confirmed']}",
            f"- authorized_submit={application_summary['authorized_submit']}",
            f"- submitted={application_summary['submitted']}",
            f"- error_submit={application_summary['error_submit']}",
            f"- cancelled={application_summary['cancelled']}",
        ]
        return "\n".join(lines)

    def review_job(self, job_id: int, action: str) -> str:
        job = self.repository.get_job(job_id)
        if job is None:
            return f"Vaga nao encontrada: id={job_id}"
        next_status, detail = resolve_review_action(job, action)
        if next_status is None:
            return detail
        self.repository.mark_status(job_id, next_status, detail=detail)
        return detail

    def create_application_draft_for_job(self, job_id: int) -> str:
        job = self.repository.get_job(job_id)
        if job is None:
            return f"Vaga nao encontrada: id={job_id}"
        existing = self.repository.get_application_by_job(job_id)
        if existing is not None:
            return (
                f"Candidatura ja existe para a vaga: application_id={existing.id} "
                f"status={existing.status} job_id={job_id}"
            )
        drafts = self.application_preparation.create_drafts_for_approved_jobs(
            [job_id],
            notes="rascunho criado via cli apos aprovacao humana",
        )
        if not drafts:
            return f"Vaga ainda nao foi aprovada para criar candidatura: id={job_id}"
        draft = drafts[0]
        return (
            f"Rascunho criado: application_id={draft.id} job_id={job_id} "
            f"status={draft.status} suporte={draft.support_level}"
        )

    def show_application_events(self, application_id: int, *, limit: int = 10) -> str:
        application = self.repository.get_application(application_id)
        if application is None:
            return f"Candidatura nao encontrada: id={application_id}"
        events = self.repository.list_application_events(application_id, limit=limit)
        if not events:
            return f"Nenhum evento encontrado para candidatura: id={application_id}"
        lines = [f"Eventos da candidatura {application_id}: {len(events)}"]
        for event in events:
            lines.append(
                f"{event.created_at or '-'} | {event.event_type} | "
                f"{event.from_status or '-'} -> {event.to_status or '-'} | "
                f"{event.detail or '-'}"
            )
        return "\n".join(lines)

    def show_application(self, application_id: int) -> str:
        application = self.repository.get_application(application_id)
        if application is None:
            return f"Candidatura nao encontrada: id={application_id}"
        job = self.repository.get_job(application.job_id)
        job_title = job.title if job is not None else "vaga nao encontrada"
        job_company = job.company if job is not None else "-"
        job_url = job.url if job is not None else "-"
        lines = [
            f"id={application.id}",
            f"status={application.status}",
            f"job_id={application.job_id}",
            f"vaga={job_title}",
            f"empresa={job_company}",
            f"suporte={application.support_level}",
            f"url={job_url}",
            f"last_preflight_detail={application.last_preflight_detail or '-'}",
            f"last_submit_detail={application.last_submit_detail or '-'}",
            f"last_error={application.last_error or '-'}",
            f"submitted_at={application.submitted_at or '-'}",
            f"notes={application.notes or '-'}",
        ]
        events = self.repository.list_application_events(application_id, limit=5)
        if events:
            lines.append("eventos_recentes:")
            for event in events:
                lines.append(
                    f"- {event.created_at or '-'} | {event.event_type} | "
                    f"{event.from_status or '-'} -> {event.to_status or '-'} | "
                    f"{event.detail or '-'}"
                )
        return "\n".join(lines)

    def transition_application(self, application_id: int, action: str) -> str:
        application = self.repository.get_application(application_id)
        if application is None:
            return f"Candidatura nao encontrada: id={application_id}"
        next_status, detail = resolve_application_action(application, action)
        if next_status is None:
            return detail
        self.repository.mark_application_status(application_id, status=next_status, event_detail=detail)
        return detail

    def authorize_application(self, application_id: int) -> str:
        return self.transition_application(application_id, "app_authorize")

    def show_latest_failure_artifacts(self, *, limit: int = 5) -> str:
        artifacts_dir = Path(self.settings.failure_artifacts_dir)
        if not artifacts_dir.exists():
            return f"Nenhum diretorio de artefatos encontrado: {artifacts_dir}"
        files = sorted(
            artifacts_dir.glob("*_meta.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not files:
            return f"Nenhum artefato de falha encontrado em: {artifacts_dir}"
        lines = [f"Artefatos recentes: {min(len(files), limit)}"]
        for path in files[:limit]:
            timestamp = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
            lines.append(f"{timestamp} | {path.name}")
        return "\n".join(lines)

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
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="Mostra um resumo operacional de vagas e candidaturas.")
    jobs_parser = subparsers.add_parser("jobs", help="Operacoes de revisao de vagas.")
    jobs_subparsers = jobs_parser.add_subparsers(dest="jobs_command", required=True)

    jobs_list_parser = jobs_subparsers.add_parser("list", help="Lista vagas por status.")
    jobs_list_parser.add_argument(
        "--status",
        choices=["all", "pending", "review", "approved_only", *sorted(VALID_STATUSES)],
        default="all",
        help="Filtra por status de vaga.",
    )

    jobs_approve_parser = jobs_subparsers.add_parser("approve", help="Aprova uma vaga coletada.")
    jobs_approve_parser.add_argument("--id", type=int, required=True, help="ID da vaga.")

    jobs_reject_parser = jobs_subparsers.add_parser("reject", help="Rejeita uma vaga coletada.")
    jobs_reject_parser.add_argument("--id", type=int, required=True, help="ID da vaga.")

    jobs_show_parser = jobs_subparsers.add_parser("show", help="Mostra o detalhe de uma vaga.")
    jobs_show_parser.add_argument("--id", type=int, required=True, help="ID da vaga.")

    applications_parser = subparsers.add_parser("applications", help="Operacoes de candidaturas.")
    applications_subparsers = applications_parser.add_subparsers(dest="applications_command", required=True)

    applications_list_parser = applications_subparsers.add_parser("list", help="Lista candidaturas.")
    applications_list_parser.add_argument(
        "--status",
        choices=["all", "ready", "review", "error", *sorted(VALID_APPLICATION_STATUSES)],
        default="all",
        help="Filtra por status de candidatura.",
    )

    applications_create_parser = applications_subparsers.add_parser(
        "create",
        help="Cria um rascunho de candidatura para uma vaga aprovada.",
    )
    applications_create_parser.add_argument("--job-id", type=int, required=True, help="ID da vaga aprovada.")

    applications_show_parser = applications_subparsers.add_parser("show", help="Mostra uma candidatura.")
    applications_show_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    applications_events_parser = applications_subparsers.add_parser(
        "events",
        help="Lista eventos recentes de uma candidatura.",
    )
    applications_events_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")
    applications_events_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Quantidade maxima de eventos retornados.",
    )

    applications_prepare_parser = applications_subparsers.add_parser(
        "prepare",
        help="Move uma candidatura de draft para ready_for_review.",
    )
    applications_prepare_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    applications_confirm_parser = applications_subparsers.add_parser(
        "confirm",
        help="Confirma uma candidatura pronta para revisao.",
    )
    applications_confirm_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    applications_cancel_parser = applications_subparsers.add_parser(
        "cancel",
        help="Cancela uma candidatura em andamento.",
    )
    applications_cancel_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    applications_artifacts_parser = applications_subparsers.add_parser(
        "artifacts",
        help="Lista artefatos recentes de falha do LinkedIn.",
    )
    applications_artifacts_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Quantidade maxima de artefatos retornados.",
    )

    applications_preflight_parser = applications_subparsers.add_parser(
        "preflight",
        help="Roda o preflight de uma candidatura confirmada.",
    )
    applications_preflight_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    applications_authorize_parser = applications_subparsers.add_parser(
        "authorize",
        help="Autoriza uma candidatura confirmada para envio real.",
    )
    applications_authorize_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    applications_submit_parser = applications_subparsers.add_parser(
        "submit",
        help="Executa o envio real de uma candidatura autorizada.",
    )
    applications_submit_parser.add_argument("--id", type=int, required=True, help="ID da candidatura.")

    args = parser.parse_args()
    if args.ciclos is not None and args.ciclos <= 0:
        parser.error("--ciclos deve ser maior que zero")
    if args.intervalo_ciclos_segundos < 0:
        parser.error("--intervalo-ciclos-segundos nao pode ser negativo")
    if args.agora and args.ciclos is not None:
        parser.error("use --agora ou --ciclos, nao ambos")
    if args.command is not None and (args.agora or args.ciclos is not None):
        parser.error("comandos operacionais nao podem ser combinados com --agora ou --ciclos")
    return args


def run() -> None:
    args = parse_args()
    if args.bootstrap_linkedin_session:
        settings = load_settings()
        asyncio.run(bootstrap_linkedin_storage_state(settings))
        return
    if args.command == "status":
        app = JobHunterApplication(enable_telegram=not args.sem_telegram)
        print(app.show_status_overview())
        return
    if args.command == "jobs":
        app = JobHunterApplication(enable_telegram=not args.sem_telegram)
        if args.jobs_command == "list":
            status = JOB_STATUS_ALIASES.get(args.status, args.status)
            print(app.list_jobs(status=status))
            return
        if args.jobs_command == "show":
            print(app.show_job(args.id))
            return
        if args.jobs_command == "approve":
            print(app.review_job(args.id, "approve"))
            return
        if args.jobs_command == "reject":
            print(app.review_job(args.id, "reject"))
            return
    if args.command == "applications":
        app = JobHunterApplication(enable_telegram=not args.sem_telegram)
        if args.applications_command == "list":
            status = APPLICATION_STATUS_ALIASES.get(args.status, args.status)
            print(app.list_applications(status=status))
            return
        if args.applications_command == "create":
            print(app.create_application_draft_for_job(args.job_id))
            return
        if args.applications_command == "show":
            print(app.show_application(args.id))
            return
        if args.applications_command == "events":
            print(app.show_application_events(args.id, limit=args.limit))
            return
        if args.applications_command == "prepare":
            print(app.transition_application(args.id, "app_prepare"))
            return
        if args.applications_command == "confirm":
            print(app.transition_application(args.id, "app_confirm"))
            return
        if args.applications_command == "cancel":
            print(app.transition_application(args.id, "app_cancel"))
            return
        if args.applications_command == "artifacts":
            print(app.show_latest_failure_artifacts(limit=args.limit))
            return
        if args.applications_command == "authorize":
            print(app.authorize_application(args.id))
            return
        if args.applications_command == "preflight":
            print(asyncio.run(app.handle_application_preflight(args.id)))
            return
        if args.applications_command == "submit":
            print(asyncio.run(app.handle_application_submit(args.id)))
            return
    asyncio.run(
        JobHunterApplication(enable_telegram=not args.sem_telegram).run(
            run_once=args.agora,
            fixed_cycles=args.ciclos,
            cycle_interval_seconds=args.intervalo_ciclos_segundos,
        )
    )
