from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CollectionRunSummary:
    total_runs: int = 0
    success_runs: int = 0
    error_runs: int = 0
    interrupted_runs: int = 0
    running_runs: int = 0
    jobs_seen: int = 0
    jobs_saved: int = 0
    errors: int = 0


@dataclass(frozen=True)
class CollectionLogSummary:
    by_source: dict[str, int]
    by_level: dict[str, int]
    recent_warnings_or_errors: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class CollectionOperationsReport:
    run_summary: CollectionRunSummary
    log_summary: CollectionLogSummary


EMPTY_COLLECTION_OPERATIONS_REPORT = CollectionOperationsReport(
    run_summary=CollectionRunSummary(),
    log_summary=CollectionLogSummary(
        by_source={},
        by_level={},
        recent_warnings_or_errors=(),
    ),
)
