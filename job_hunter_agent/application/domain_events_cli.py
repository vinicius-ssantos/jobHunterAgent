from __future__ import annotations

import json
from pathlib import Path

from job_hunter_agent.core.event_bus import LocalNdjsonEventBus
from job_hunter_agent.core.events import (
    ApplicationAuthorizedV1,
    ApplicationBlockedV1,
    ApplicationPreflightCompletedV1,
    ApplicationSubmittedV1,
    DomainEvent,
    JobCollectedV1,
    JobReviewRequestedV1,
    JobReviewedV1,
    JobScoredV1,
    event_to_dict,
)


def render_domain_events(
    *,
    path: Path,
    limit: int = 20,
    event_type: str = "",
    correlation_id: str = "",
    as_json: bool = False,
) -> str:
    events = _filter_events(
        LocalNdjsonEventBus(path).read_all(),
        event_type=event_type,
        correlation_id=correlation_id,
    )
    if not events:
        if as_json:
            return "[]"
        return f"Nenhum evento de dominio encontrado em {path}"
    bounded_limit = max(1, limit)
    selected = tuple(events[-bounded_limit:])
    if as_json:
        return json.dumps([event_to_dict(event) for event in selected], ensure_ascii=False, indent=2)
    lines = [f"Eventos de dominio: {len(selected)} de {len(events)} arquivo={path}"]
    for event in selected:
        lines.append(_render_event_line(event))
    return "\n".join(lines)


def _filter_events(
    events: tuple[DomainEvent, ...],
    *,
    event_type: str = "",
    correlation_id: str = "",
) -> tuple[DomainEvent, ...]:
    normalized_event_type = event_type.strip()
    normalized_correlation_id = correlation_id.strip()
    filtered = events
    if normalized_event_type:
        filtered = tuple(event for event in filtered if event.event_type == normalized_event_type)
    if normalized_correlation_id:
        filtered = tuple(event for event in filtered if event.correlation_id == normalized_correlation_id)
    return filtered


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
    if isinstance(event, ApplicationPreflightCompletedV1):
        return (
            f"{base} application_id={event.application_id} job_id={event.job_id} "
            f"outcome={event.outcome} status={event.application_status}"
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
