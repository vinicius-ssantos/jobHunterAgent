from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from job_hunter_agent.application.composition import create_collection_service, create_repository
from job_hunter_agent.application.cycle_workers import JobCollectedV1
from job_hunter_agent.application.worker_runtime import (
    DEFAULT_WORKER_DLQ_PATH,
    append_worker_dlq_event,
    build_worker_dlq_event,
    run_with_retry,
)
from job_hunter_agent.core.domain import CollectionReport
from job_hunter_agent.core.settings import Settings, load_settings


def build_job_collected_event(*, run_id: int, report: CollectionReport) -> JobCollectedV1:
    return JobCollectedV1(
        run_id=run_id,
        jobs=tuple(report.jobs),
        jobs_seen=report.jobs_seen,
        jobs_saved=report.jobs_saved,
        errors=report.errors,
    )


def append_event_ndjson(*, output_path: Path, event: JobCollectedV1) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(event)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(serialized)
        handle.write("\n")


async def run_collector_worker_once(*, output_path: Path, settings: Settings | None = None) -> str:
    runtime_settings = settings or load_settings()
    repository = create_repository(runtime_settings)
    collector = create_collection_service(settings=runtime_settings, repository=repository)
    run = repository.start_collection_run()
    dlq_path = DEFAULT_WORKER_DLQ_PATH
    try:
        report = await run_with_retry(
            operation="collector.collect_new_jobs_report",
            action=collector.collect_new_jobs_report,
        )
        repository.finish_collection_run(
            run.id,
            status="success",
            jobs_seen=report.jobs_seen,
            jobs_saved=report.jobs_saved,
            errors=report.errors,
        )
    except Exception as exc:
        repository.finish_collection_run(
            run.id,
            status="error",
            jobs_seen=0,
            jobs_saved=0,
            errors=1,
        )
        append_worker_dlq_event(
            output_path=dlq_path,
            event=build_worker_dlq_event(
                worker="collector_worker",
                operation="collect_new_jobs_report",
                payload={"run_id": run.id, "output_path": str(output_path)},
                error=str(exc),
            ),
        )
        raise
    event = build_job_collected_event(run_id=run.id, report=report)
    append_event_ndjson(output_path=output_path, event=event)
    return (
        f"collector_worker: evento JobCollectedV1 emitido "
        f"run_id={run.id} vistas={report.jobs_seen} persistidas={report.jobs_saved} "
        f"arquivo={output_path}"
    )
