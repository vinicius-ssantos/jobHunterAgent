from __future__ import annotations

from pathlib import Path
from typing import Protocol

from job_hunter_agent.core.events import (
    ApplicationAuthorizedV1,
    ApplicationBlockedV1,
    ApplicationDraftCreatedV1,
    ApplicationPreflightCompletedV1,
    ApplicationSubmittedV1,
    DomainEvent,
    JobCollectedV1,
    JobReviewRequestedV1,
    JobReviewedV1,
    JobScoredV1,
    event_from_json,
    event_to_json,
)


class EventBusPort(Protocol):
    def publish(self, event: DomainEvent) -> None:
        raise NotImplementedError

    def read_all(self) -> tuple[DomainEvent, ...]:
        raise NotImplementedError


class LocalNdjsonEventBus:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def publish(self, event: DomainEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(event_to_json(event))
            handle.write("\n")

    def read_all(self) -> tuple[DomainEvent, ...]:
        if not self.path.exists():
            return ()
        events: list[DomainEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = event_from_json(line)
            except (ValueError, TypeError):
                continue
            events.append(event)
        return tuple(events)

    def read_job_collected(self) -> tuple[JobCollectedV1, ...]:
        return tuple(event for event in self.read_all() if isinstance(event, JobCollectedV1))

    def read_job_scored(self) -> tuple[JobScoredV1, ...]:
        return tuple(event for event in self.read_all() if isinstance(event, JobScoredV1))

    def read_job_review_requested(self) -> tuple[JobReviewRequestedV1, ...]:
        return tuple(event for event in self.read_all() if isinstance(event, JobReviewRequestedV1))

    def read_job_reviewed(self) -> tuple[JobReviewedV1, ...]:
        return tuple(event for event in self.read_all() if isinstance(event, JobReviewedV1))

    def read_application_authorized(self) -> tuple[ApplicationAuthorizedV1, ...]:
        return tuple(event for event in self.read_all() if isinstance(event, ApplicationAuthorizedV1))

    def read_application_draft_created(self) -> tuple[ApplicationDraftCreatedV1, ...]:
        return tuple(event for event in self.read_all() if isinstance(event, ApplicationDraftCreatedV1))

    def read_application_preflight_completed(self) -> tuple[ApplicationPreflightCompletedV1, ...]:
        return tuple(event for event in self.read_all() if isinstance(event, ApplicationPreflightCompletedV1))

    def read_application_submitted(self) -> tuple[ApplicationSubmittedV1, ...]:
        return tuple(event for event in self.read_all() if isinstance(event, ApplicationSubmittedV1))

    def read_application_blocked(self) -> tuple[ApplicationBlockedV1, ...]:
        return tuple(event for event in self.read_all() if isinstance(event, ApplicationBlockedV1))
