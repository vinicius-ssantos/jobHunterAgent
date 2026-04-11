from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional, Protocol

from job_hunter_agent.core.domain import JobApplication, JobPosting
from job_hunter_agent.infrastructure.notifier_rendering import (
    build_application_action_rows as rendering_build_application_action_rows,
    build_application_card_message as rendering_build_application_card_message,
    build_application_preview_line as rendering_build_application_preview_line,
    build_application_queue_message as rendering_build_application_queue_message,
    build_job_card_message as rendering_build_job_card_message,
    build_missing_application_reply as rendering_build_missing_application_reply,
    build_missing_job_reply as rendering_build_missing_job_reply,
)
from job_hunter_agent.infrastructure.notifier_callbacks import NotifierCallbackService
from job_hunter_agent.infrastructure.repository import JobRepository
from job_hunter_agent.llm.review_rationale import ReviewRationaleFormatter
from job_hunter_agent.application.review_workflow import (
    resolve_application_action as workflow_resolve_application_action,
    resolve_application_preflight_request as workflow_resolve_application_preflight_request,
    resolve_application_submit_request as workflow_resolve_application_submit_request,
    resolve_review_action as workflow_resolve_review_action,
)
from job_hunter_agent.core.settings import Settings


logger = logging.getLogger(__name__)
ApprovalCallback = Callable[[list[int]], Awaitable[None]]
ApplicationPreflightCallback = Callable[[int], Awaitable[str]]
ApplicationSubmitCallback = Callable[[int], Awaitable[str]]

build_job_card_message = rendering_build_job_card_message
build_missing_job_reply = rendering_build_missing_job_reply
build_missing_application_reply = rendering_build_missing_application_reply
build_application_queue_message = rendering_build_application_queue_message
build_application_preview_line = rendering_build_application_preview_line
build_application_card_message = rendering_build_application_card_message
build_application_action_rows = rendering_build_application_action_rows
resolve_review_action = workflow_resolve_review_action
resolve_application_preflight_request = workflow_resolve_application_preflight_request
resolve_application_submit_request = workflow_resolve_application_submit_request
resolve_application_action = workflow_resolve_application_action


def validate_telegram_settings(settings: Settings) -> None:
    token = settings.telegram_token.strip()
    chat_id = settings.telegram_chat_id.strip()
    if not token or token == "SEU_TOKEN_AQUI":
        raise ValueError("Preencha JOB_HUNTER_TELEGRAM_TOKEN para usar o Telegram.")
    if not chat_id or chat_id == "SEU_CHAT_ID_AQUI":
        raise ValueError("Preencha JOB_HUNTER_TELEGRAM_CHAT_ID para usar o Telegram.")


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
        on_application_preflight: Optional[ApplicationPreflightCallback] = None,
        on_application_submit: Optional[ApplicationSubmitCallback] = None,
        review_rationale_formatter: ReviewRationaleFormatter | None = None,
    ) -> None:
        validate_telegram_settings(settings)
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
        self.on_application_preflight = on_application_preflight
        self.on_application_submit = on_application_submit
        self.review_rationale_formatter = review_rationale_formatter
        self.callback_service = NotifierCallbackService(repository)
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
        structured_rationale = None
        if self.review_rationale_formatter is not None:
            try:
                structured_rationale = self.review_rationale_formatter.format(job)
            except Exception:
                structured_rationale = None
        message = build_job_card_message(job, structured_rationale)
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
        try:
            outcome = self.callback_service.handle(query.data)
        except Exception:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("Falha ao processar a acao solicitada.")
            return

        if outcome.clear_reply_markup:
            await query.edit_message_reply_markup(reply_markup=None)
        if outcome.requested_preflight_application_id is not None:
            if not self.on_application_preflight:
                await query.message.reply_text("Preflight de candidatura indisponivel nesta execucao.")
                return
            await query.message.reply_text(
                await self.on_application_preflight(outcome.requested_preflight_application_id)
            )
            return
        if outcome.requested_submit_application_id is not None:
            if not self.on_application_submit:
                await query.message.reply_text("Submissao real indisponivel nesta execucao.")
                return
            await query.message.reply_text(
                await self.on_application_submit(outcome.requested_submit_application_id)
            )
            return
        await query.message.reply_text(outcome.reply_text)
        if outcome.approved_job_ids and self.on_approved:
            await self.on_approved(list(outcome.approved_job_ids))

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
        applications: list[JobApplication] = []
        for status in ("draft", "ready_for_review", "confirmed", "authorized_submit"):
            applications.extend(self.repository.list_applications_by_status(status)[:5])
        if not applications:
            return
        for application in applications:
            await self._send_application_card(application)

    async def _send_application_card(self, application: JobApplication) -> None:
        message = build_application_card_message(self.repository, application)
        keyboard = self._inline_keyboard_markup(build_application_action_rows(application, self._inline_keyboard_button))
        await self.application.bot.send_message(
            chat_id=self.settings.telegram_chat_id,
            text=message,
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
