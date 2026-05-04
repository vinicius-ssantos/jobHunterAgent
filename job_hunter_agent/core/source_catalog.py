from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable


class CollectionMethod(StrEnum):
    API = "api"
    SCRAPING = "scraping"
    PLAYWRIGHT = "playwright"
    MANUAL = "manual"


class SourceRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourcePriority(StrEnum):
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"


DEFAULT_SOURCE_CATALOG_PATH = Path("source_catalog.json")


class SourceCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class JobSource:
    name: str
    method: CollectionMethod
    priority: SourcePriority
    risk: SourceRisk
    requires_login: bool = False
    has_rate_limit_risk: bool = False
    has_captcha_risk: bool = False
    notes: str = ""

    @property
    def safe_for_unattended_collection(self) -> bool:
        return (
            self.method in {CollectionMethod.API, CollectionMethod.SCRAPING}
            and not self.requires_login
            and self.risk != SourceRisk.HIGH
        )


_DEFAULT_SOURCES: tuple[JobSource, ...] = (
    JobSource(
        name="LinkedIn",
        method=CollectionMethod.PLAYWRIGHT,
        priority=SourcePriority.P0,
        risk=SourceRisk.HIGH,
        requires_login=True,
        has_rate_limit_risk=True,
        has_captcha_risk=True,
        notes="Use only with human gates for login and external actions.",
    ),
    JobSource(
        name="Gupy",
        method=CollectionMethod.SCRAPING,
        priority=SourcePriority.P0,
        risk=SourceRisk.MEDIUM,
        has_rate_limit_risk=True,
        notes="Public job pages can be collected without submission automation.",
    ),
    JobSource(
        name="Greenhouse",
        method=CollectionMethod.API,
        priority=SourcePriority.P1,
        risk=SourceRisk.LOW,
        notes="Prefer public board API endpoints when available.",
    ),
    JobSource(
        name="Lever",
        method=CollectionMethod.API,
        priority=SourcePriority.P1,
        risk=SourceRisk.LOW,
        notes="Prefer public postings API endpoints when available.",
    ),
    JobSource(
        name="Manual referral/community",
        method=CollectionMethod.MANUAL,
        priority=SourcePriority.P2,
        risk=SourceRisk.LOW,
        notes="Manual intake keeps unsupported or private sources explicit.",
    ),
)


def list_default_job_sources() -> tuple[JobSource, ...]:
    return _DEFAULT_SOURCES


def find_job_source(name: str, sources: Iterable[JobSource] | None = None) -> JobSource | None:
    normalized_name = name.strip().lower()
    for source in sources or _DEFAULT_SOURCES:
        if source.name.lower() == normalized_name:
            return source
    return None


def sources_by_priority(
    priority: SourcePriority,
    sources: Iterable[JobSource] | None = None,
) -> tuple[JobSource, ...]:
    return tuple(source for source in (sources or _DEFAULT_SOURCES) if source.priority == priority)


def safe_unattended_sources(sources: Iterable[JobSource] | None = None) -> tuple[JobSource, ...]:
    return tuple(
        source
        for source in (sources or _DEFAULT_SOURCES)
        if source.safe_for_unattended_collection
    )
