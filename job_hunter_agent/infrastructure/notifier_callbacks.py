from __future__ import annotations

from dataclasses import dataclass

from job_hunter_agent.application.review_workflow import (
    resolve_application_action,
    resolve_application_preflight_request,
    resolve_application_submit_request,
    resolve_review_action,
)
from job_hunter_agent.infrastructure.notifier_rendering import (
    build_missing_application_reply,
    build_missing_job_reply,
)
from job_hunter_agent.infrastructure.repository import JobRepository


@dataclass(frozen=True)
class NotifierCallbackOutcome:
    reply_text: str
    clear_reply_markup: bool = True
    approved_job_ids: tuple[int, ...] = ()
    requested_preflight_application_id: int | None = None
    requested_submit_application_id: int | None = None


class NotifierCallbackService:
    def __init__(self, repository: JobRepository) -> None:
        self.repository = repository

    def handle(self, callback_data: str) -> NotifierCallbackOutcome:
        action, target_id_text = callback_data.split(":", maxsplit=1)
        target_id = int(target_id_text)

        if action in {"approve", "reject"}:
            return self._handle_job_review(action=action, job_id=target_id)

        return self._handle_application_action(action=action, application_id=target_id)

    def _handle_job_review(self, *, action: str, job_id: int) -> NotifierCallbackOutcome:
        job = self.repository.get_job(job_id)
        if not job:
            return NotifierCallbackOutcome(reply_text=build_missing_job_reply(job_id))

        next_status, reply_text = resolve_review_action(job, action)
        if next_status is None:
            return NotifierCallbackOutcome(reply_text=reply_text)

        self.repository.mark_status(job_id, next_status, detail=reply_text)
        approved_job_ids = (job_id,) if next_status == "approved" else ()
        return NotifierCallbackOutcome(
            reply_text=reply_text,
            approved_job_ids=approved_job_ids,
        )

    def _handle_application_action(self, *, action: str, application_id: int) -> NotifierCallbackOutcome:
        application = self.repository.get_application(application_id)
        if not application:
            return NotifierCallbackOutcome(reply_text=build_missing_application_reply(application_id))

        if action == "app_preflight":
            allowed, reply_text = resolve_application_preflight_request(application)
            if not allowed:
                return NotifierCallbackOutcome(reply_text=reply_text)
            return NotifierCallbackOutcome(
                reply_text=reply_text,
                requested_preflight_application_id=application_id,
            )

        if action == "app_submit":
            allowed, reply_text = resolve_application_submit_request(application)
            if not allowed:
                return NotifierCallbackOutcome(reply_text=reply_text)
            return NotifierCallbackOutcome(
                reply_text=reply_text,
                requested_submit_application_id=application_id,
            )

        next_status, reply_text = resolve_application_action(application, action)
        if next_status is None:
            return NotifierCallbackOutcome(reply_text=reply_text)

        self.repository.mark_application_status(application_id, status=next_status, event_detail=reply_text)
        return NotifierCallbackOutcome(reply_text=reply_text)
