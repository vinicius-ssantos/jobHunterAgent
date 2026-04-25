from __future__ import annotations

from pathlib import Path
from typing import Protocol

from job_hunter_agent.core.events import (
    JobCollectedV1,
    JobScoredV1,
    event_from_json,
    event_to_json,
)

DomainEvent = JobCollectedV1 | JobScoredV1


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
