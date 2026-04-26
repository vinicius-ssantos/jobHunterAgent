from __future__ import annotations

from pathlib import Path

from job_hunter_agent.core.event_bus import LocalNdjsonEventBus
from job_hunter_agent.core.events import (
    ApplicationAuthorizedV1,
    ApplicationBlockedV1,
    ApplicationSubmittedV1,
    DomainEvent,
    JobCollectedV1,
    JobReviewRequestedV1,
    JobReviewedV1,
    JobScoredV1,
)


def render_domain_events(*, path: Path, limit: int = 20) -> str:
    events = LocalNdjsonEventBus(path).read_all()
    if not events:
        return f"Nenhum evento de dominio encontrado em {path}"
    bounded_limit = max(1, limit)
    selected = tuple(events[-bounded_limit:])
    lines = [f"Eventos de dominio: {len(selected)} de {len(events)} arquivo={path}"]
    for event in selected:
        lines.append(_render_event_line(event))
    return "\n".join(lines)


def _render_event_line(event: DomainEvent) -> str:
    base = (
        f"- {event.occurred_at} {event.event_type} "
        f"event_id={event.event_id} correlation_id={event.correlation_id or '-'}"
    )
    if isinstance(event, JobCollectedV1):
        return (
            f"{base} run_id={event.run_id} jobs_seen={event.jobs_seen} "
            f"jobs_saved={event.jobs_saved} errors={event.errors}"
        )
    if isinstance(event, JobScoredV1):
        return (
            f"{base} run_id={event.run_id} external_key={event.external_key} "
            f"accepted={event.accepted} relevance={event.relevance}"
        )
    if isinstance(event, JobReviewRequestedV1):
        return (
            f"{base} job_id={event.job_id} external_key={event.external_key} "
            f"source_site={event.source_site} relevance={event.relevance} reason={event.reason or '-'}"
        )
    if isinstance(event, JobReviewedV1):
        return (
            f"{base} job_id={event.job_id} decision={event.decision} "
            f"status={event.status} reviewed_by={event.reviewed_by or '-'}"
        )
    if isinstance(event, ApplicationAuthorizedV1):
        return (
            f"{base} application_id={event.application_id} job_id={event.job_id} "
            f"authorized_by={event.authorized_by or '-'} source={event.authorization_source} status={event.status}"
        )
    if isinstance(event, ApplicationSubmittedV1):
        return (
            f"{base} application_id={event.application_id} job_id={event.job_id} "
            f"portal={event.portal} confirmation={event.confirmation_reference or '-'}"
        )
    if isinstance(event, ApplicationBlockedV1):
        return (
            f"{base} application_id={event.application_id} job_id={event.job_id} "
            f"reason={event.reason} retryable={event.retryable}"
        )
    return base
