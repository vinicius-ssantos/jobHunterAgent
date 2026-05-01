from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def build_collection_operations_report(repository: object, *, since: str) -> CollectionOperationsReport:
    db_path = getattr(repository, "db_path", None)
    if db_path is None:
        return EMPTY_COLLECTION_OPERATIONS_REPORT
    path = Path(db_path)
    if not path.exists():
        return EMPTY_COLLECTION_OPERATIONS_REPORT
    with sqlite3.connect(path) as connection:
        if not _table_exists(connection, "collection_runs") or not _table_exists(connection, "collection_logs"):
            return EMPTY_COLLECTION_OPERATIONS_REPORT
        return CollectionOperationsReport(
            run_summary=_build_run_summary(connection, since=since),
            log_summary=_build_log_summary(connection, since=since),
        )


def render_collection_operations_report(report: CollectionOperationsReport) -> str:
    run_summary = report.run_summary
    log_summary = report.log_summary
    lines = [
        "coleta:",
        f"- ciclos={run_summary.total_runs}",
        f"- ciclos_success={run_summary.success_runs}",
        f"- ciclos_error={run_summary.error_runs}",
        f"- ciclos_interrupted={run_summary.interrupted_runs}",
        f"- ciclos_running={run_summary.running_runs}",
        f"- jobs_seen={run_summary.jobs_seen}",
        f"- jobs_saved={run_summary.jobs_saved}",
        f"- errors={run_summary.errors}",
    ]
    if log_summary.by_source:
        lines.append("coleta_por_fonte:")
        for source_site, count in sorted(log_summary.by_source.items()):
            lines.append(f"- {source_site}={count}")
    if log_summary.by_level:
        lines.append("logs_por_nivel:")
        for level, count in sorted(log_summary.by_level.items()):
            lines.append(f"- {level}={count}")
    if log_summary.recent_warnings_or_errors:
        lines.append("logs_recentes_warning_error:")
        for item in log_summary.recent_warnings_or_errors:
            lines.append(
                f"- {item['created_at']} | {item['source_site']} | {item['level']} | {item['message']}"
            )
    return "\n".join(lines)


def _build_run_summary(connection: sqlite3.Connection, *, since: str) -> CollectionRunSummary:
    query = """
        SELECT
            COUNT(*),
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'interrupted' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END),
            SUM(jobs_seen),
            SUM(jobs_saved),
            SUM(errors)
        FROM collection_runs
        WHERE started_at >= ?
    """
    row = connection.execute(query, (since,)).fetchone()
    return CollectionRunSummary(
        total_runs=_int_value(row[0]),
        success_runs=_int_value(row[1]),
        error_runs=_int_value(row[2]),
        interrupted_runs=_int_value(row[3]),
        running_runs=_int_value(row[4]),
        jobs_seen=_int_value(row[5]),
        jobs_saved=_int_value(row[6]),
        errors=_int_value(row[7]),
    )


def _build_log_summary(connection: sqlite3.Connection, *, since: str) -> CollectionLogSummary:
    source_rows = connection.execute(
        "SELECT source_site, COUNT(*) FROM collection_logs WHERE created_at >= ? GROUP BY source_site ORDER BY source_site",
        (since,),
    ).fetchall()
    level_rows = connection.execute(
        "SELECT level, COUNT(*) FROM collection_logs WHERE created_at >= ? GROUP BY level ORDER BY level",
        (since,),
    ).fetchall()
    recent_rows = connection.execute(
        """
        SELECT created_at, source_site, level, message
        FROM collection_logs
        WHERE created_at >= ? AND LOWER(level) IN ('warning', 'warn', 'error')
        ORDER BY id DESC
        LIMIT 5
        """,
        (since,),
    ).fetchall()
    return CollectionLogSummary(
        by_source={str(source): int(count) for source, count in source_rows},
        by_level={str(level): int(count) for level, count in level_rows},
        recent_warnings_or_errors=tuple(
            {
                "created_at": str(created_at or ""),
                "source_site": str(source_site or ""),
                "level": str(level or ""),
                "message": str(message or ""),
            }
            for created_at, source_site, level, message in recent_rows
        ),
    )


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _int_value(value: Any) -> int:
    return int(value or 0)
