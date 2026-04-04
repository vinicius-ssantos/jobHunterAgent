from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional, Protocol

from job_hunter_agent.domain import JobApplication, JobPosting
from job_hunter_agent.repository import JobRepository
from job_hunter_agent.settings import Settings


logger = logging.getLogger(__name__)
ApprovalCallback = Callable[[list[int]], Awaitable[None]]


class ReviewNotifier(Protocol):
    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    async def send_text(self, text: str) -> None:
        raise NotImplementedError

    async def notify_jobs_for_review(self, jobs: list[JobPosting]) -> None:
        raise NotImplementedError


class NullNotifier:
    async def start(self) -> None:
        logger.info("Notifier desabilitado para esta execucao.")

    async def stop(self) -> None:
        return

    async def send_text(self, text: str) -> None:
        logger.info("Mensagem suprimida (sem Telegram): %s", text)

    async def notify_jobs_for_review(self, jobs: list[JobPosting]) -> None:
        if not jobs:
            logger.info("Nenhuma vaga nova passou na triagem.")
            return
        logger.info("Telegram desabilitado. %s vagas ficaram apenas persistidas localmente.", len(jobs))


class TelegramNotifier:
    def __init__(
        self,
        settings: Settings,
        repository: JobRepository,
        on_approved: Optional[ApprovalCallback] = None,
    ) -> None:
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            from telegram.ext import Application, CallbackQueryHandler, CommandHandler
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias do Telegram nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc

        self.settings = settings
        self.repository = repository
        self.on_approved = on_approved
        self._inline_keyboard_button = InlineKeyboardButton
        self._inline_keyboard_markup = InlineKeyboardMarkup
        self.application = Application.builder().token(settings.telegram_token).build()
        self.application.add_handler(CommandHandler("start", self._command_start))
        self.application.add_handler(CommandHandler("status", self._command_status))
        self.application.add_handler(CommandHandler("pendentes", self._command_pending))
        self.application.add_handler(CommandHandler("recentes", self._command_recent))
        self.application.add_handler(CommandHandler("candidaturas", self._command_applications))
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))

    async def start(self) -> None:
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram polling iniciado.")

    async def stop(self) -> None:
        if self.application.updater:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

    async def send_text(self, text: str) -> None:
        await self.application.bot.send_message(
            chat_id=self.settings.telegram_chat_id,
            text=text,
            parse_mode="Markdown",
        )

    async def notify_jobs_for_review(self, jobs: list[JobPosting]) -> None:
        if not jobs:
            await self.send_text("Nenhuma vaga nova passou na triagem.")
            return
        await self.send_text(f"*{len(jobs)} vagas novas* passaram na triagem. Revise abaixo:")
        for job in jobs:
            await self._send_job_card(job)

    async def _send_job_card(self, job: JobPosting) -> None:
        keyboard = self._inline_keyboard_markup(
            [
                [
                    self._inline_keyboard_button("Aprovar", callback_data=f"approve:{job.id}"),
                    self._inline_keyboard_button("Ignorar", callback_data=f"reject:{job.id}"),
                ]
            ]
        )
        message = build_job_card_message(job)
        await self.application.bot.send_message(
            chat_id=self.settings.telegram_chat_id,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )

    async def _handle_callback(self, update, context) -> None:
        query = update.callback_query
        await query.answer()
        action, job_id_text = query.data.split(":", maxsplit=1)
        job_id = int(job_id_text)
        job = self.repository.get_job(job_id)
        if not job:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(build_missing_job_reply(job_id))
            return

        next_status, reply_text = resolve_review_action(job, action)
        if next_status is None:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(reply_text)
            return

        if next_status == "approved":
            self.repository.mark_status(job_id, next_status)
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(reply_text)
            if self.on_approved:
                await self.on_approved([job_id])
        elif next_status == "rejected":
            self.repository.mark_status(job_id, next_status)
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(reply_text)

    async def _command_start(self, update, context) -> None:
        await update.message.reply_text(
            "Job Hunter Agent ativo.\n/status para resumo geral.\n/pendentes para vagas aguardando revisao."
        )

    async def _command_status(self, update, context) -> None:
        summary = self.repository.summary()
        await update.message.reply_text(
            "\n".join(
                [
                    "Resumo atual:",
                    f"Total: {summary['total']}",
                    f"Em revisao: {summary['collected']}",
                    f"Aprovadas: {summary['approved']}",
                    f"Rejeitadas: {summary['rejected']}",
                    f"Erros de coleta: {summary['error_collect']}",
                ]
            )
        )

    async def _command_pending(self, update, context) -> None:
        jobs = self.repository.list_jobs_by_status("collected")
        if not jobs:
            await update.message.reply_text("Nao ha vagas pendentes de revisao.")
            return
        preview_lines = [f"{job.id}: {job.title} - {job.company}" for job in jobs[:10]]
        await update.message.reply_text("Pendentes:\n" + "\n".join(preview_lines))

    async def _command_recent(self, update, context) -> None:
        jobs = self.repository.list_recent_jobs(limit=10)
        if not jobs:
            await update.message.reply_text("Nao ha vagas recentes registradas.")
            return
        preview_lines = [f"{job.id}: {job.title} - {job.company} [{job.status}]" for job in jobs]
        await update.message.reply_text("Recentes:\n" + "\n".join(preview_lines))

    async def _command_applications(self, update, context) -> None:
        await update.message.reply_text(build_application_queue_message(self.repository))


def resolve_review_action(job: JobPosting, action: str) -> tuple[str | None, str]:
    if action == "approve":
        if job.status == "approved":
            return None, f"Vaga ja estava aprovada: {job.title} - {job.company}"
        if job.status == "rejected":
            return None, f"Vaga ja estava rejeitada: {job.title} - {job.company}"
        return "approved", f"Vaga aprovada: {job.title} - {job.company}"

    if action == "reject":
        if job.status == "rejected":
            return None, f"Vaga ja estava rejeitada: {job.title} - {job.company}"
        if job.status == "approved":
            return None, f"Vaga ja estava aprovada: {job.title} - {job.company}"
        return "rejected", f"Vaga ignorada: {job.title} - {job.company}"

    return None, "Acao de revisao invalida."


def build_job_card_message(job: JobPosting) -> str:
    return (
        f"*{job.title}*\n"
        f"Empresa: {job.company}\n"
        f"Local: {job.location} | Modalidade: {job.work_mode}\n"
        f"Salario: {job.salary_text}\n"
        f"Relevancia: {job.relevance}/10\n"
        f"Motivo: {job.rationale}\n"
        f"Resumo: {job.summary}\n"
        f"[Abrir vaga]({job.url})"
    )


def build_missing_job_reply(job_id: int) -> str:
    return f"Vaga nao encontrada ou ja removida. id={job_id}"


def build_application_queue_message(repository: JobRepository) -> str:
    summary = repository.application_summary()
    tracked_statuses = ("draft", "ready_for_review", "confirmed")
    preview_lines: list[str] = []
    for status in tracked_statuses:
        applications = repository.list_applications_by_status(status)
        for application in applications[:3]:
            preview_lines.append(build_application_preview_line(repository, application))
    lines = [
        "Candidaturas:",
        f"Total: {summary['total']}",
        f"Rascunhos: {summary['draft']}",
        f"Prontas para revisao: {summary['ready_for_review']}",
        f"Confirmadas: {summary['confirmed']}",
        f"Enviadas: {summary['submitted']}",
        f"Com erro: {summary['error_submit']}",
        f"Canceladas: {summary['cancelled']}",
    ]
    if preview_lines:
        lines.append("")
        lines.append("Fila atual:")
        lines.extend(preview_lines)
    else:
        lines.append("")
        lines.append("Nao ha rascunhos ou candidaturas em andamento.")
    return "\n".join(lines)


def build_application_preview_line(repository: JobRepository, application: JobApplication) -> str:
    job = repository.get_job(application.job_id)
    if not job:
        return f"{application.job_id}: vaga ausente [{application.status}]"
    return (
        f"{job.id}: {job.title} - {job.company} "
        f"[{application.status} | {application.support_level}]"
    )
