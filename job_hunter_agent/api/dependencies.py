from __future__ import annotations

from fastapi import Depends

from job_hunter_agent.application.composition import create_domain_event_bus, create_repository
from job_hunter_agent.core.event_bus import EventBusPort
from job_hunter_agent.core.settings import Settings, load_settings
from job_hunter_agent.infrastructure.repository import JobRepository


def get_settings() -> Settings:
    return load_settings()


def get_repository(settings: Settings = Depends(get_settings)) -> JobRepository:
    return create_repository(settings)


def get_domain_event_bus(settings: Settings = Depends(get_settings)) -> EventBusPort | None:
    return create_domain_event_bus(settings)
