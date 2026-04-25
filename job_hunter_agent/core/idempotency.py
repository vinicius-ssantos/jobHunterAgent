from __future__ import annotations

from job_hunter_agent.core.events import DomainEvent, JobCollectedV1


def normalize_idempotency_part(value: object) -> str:
    return str(value or "").strip()


def build_event_subject_key(*, event_type: str, event_version: int, subject: str) -> str:
    normalized_event_type = normalize_idempotency_part(event_type)
    normalized_subject = normalize_idempotency_part(subject)
    return f"{normalized_event_type}:v{int(event_version)}:{normalized_subject}"


def build_job_scoring_key(*, event: JobCollectedV1, external_key: str) -> str:
    subject = f"run_id={event.run_id}:external_key={normalize_idempotency_part(external_key)}"
    return build_event_subject_key(
        event_type="JobScoring",
        event_version=1,
        subject=subject,
    )


def build_event_processing_key(*, event: DomainEvent, subject: str = "") -> str:
    event_subject = normalize_idempotency_part(subject) or normalize_idempotency_part(event.event_id)
    return build_event_subject_key(
        event_type=event.event_type,
        event_version=event.event_version,
        subject=event_subject,
    )
