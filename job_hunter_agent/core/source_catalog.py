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


def _required_text(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SourceCatalogError(f"source entry must define a non-empty {field!r}")
    return value.strip()


def _optional_bool(data: dict[str, Any], field: str) -> bool:
    value = data.get(field, False)
    if not isinstance(value, bool):
        raise SourceCatalogError(f"source entry field {field!r} must be a boolean")
    return value


def parse_job_source(data: dict[str, Any]) -> JobSource:
    try:
        method = CollectionMethod(_required_text(data, "method"))
        priority = SourcePriority(_required_text(data, "priority"))
        risk = SourceRisk(_required_text(data, "risk"))
    except ValueError as exc:
        raise SourceCatalogError(f"invalid source catalog enum value: {exc}") from exc

    notes = data.get("notes", "")
    if not isinstance(notes, str):
        raise SourceCatalogError("source entry field 'notes' must be a string")

    return JobSource(
        name=_required_text(data, "name"),
        method=method,
        priority=priority,
        risk=risk,
        requires_login=_optional_bool(data, "requires_login"),
        has_rate_limit_risk=_optional_bool(data, "has_rate_limit_risk"),
        has_captcha_risk=_optional_bool(data, "has_captcha_risk"),
        notes=notes.strip(),
    )


def parse_job_sources(payload: Any) -> tuple[JobSource, ...]:
    if not isinstance(payload, dict):
        raise SourceCatalogError("source catalog root must be an object")
    entries = payload.get("sources")
    if not isinstance(entries, list):
        raise SourceCatalogError("source catalog must define a 'sources' list")
    sources = tuple(parse_job_source(entry) for entry in entries if isinstance(entry, dict))
    if len(sources) != len(entries):
        raise SourceCatalogError("every source catalog entry must be an object")
    if not sources:
        raise SourceCatalogError("source catalog must define at least one source")
    names = [source.name.lower() for source in sources]
    if len(names) != len(set(names)):
        raise SourceCatalogError("source catalog must not contain duplicate source names")
    return tuple(sorted(sources, key=lambda source: (source.priority.value, source.name.lower())))


def load_job_sources(path: Path | str = DEFAULT_SOURCE_CATALOG_PATH) -> tuple[JobSource, ...]:
    catalog_path = Path(path)
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceCatalogError(f"source catalog file not found: {catalog_path}") from exc
    except json.JSONDecodeError as exc:
        raise SourceCatalogError(f"source catalog file is not valid JSON: {catalog_path}") from exc
    return parse_job_sources(payload)


def list_default_job_sources() -> tuple[JobSource, ...]:
    if DEFAULT_SOURCE_CATALOG_PATH.exists():
        return load_job_sources(DEFAULT_SOURCE_CATALOG_PATH)
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
