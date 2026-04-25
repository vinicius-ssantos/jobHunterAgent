from __future__ import annotations

import logging
from pathlib import Path

from job_hunter_agent.application.composition import create_collection_service, create_repository
from job_hunter_agent.application.worker_runtime import (
    DEFAULT_WORKER_DLQ_PATH,
    append_worker_dlq_event,
    build_worker_dlq_event,
    run_with_retry,
)
from job_hunter_agent.core.domain import CollectionReport
from job_hunter_agent.core.event_bus import EventBusPort, LocalNdjsonEventBus
from job_hunter_agent.core.events import JobCollectedV1
from job_hunter_agent.core.settings import Settings, load_settings

logger = logging.getLogger(__name__)


def build_job_collected_event(*, run_id: int, report: CollectionReport) -> JobCollectedV1:
    return JobCollectedV1(
        run_id=run_id,
        jobs=tuple(report.jobs),
        jobs_seen=report.jobs_seen,
        jobs_saved=report.jobs_saved,
        errors=report.errors,
        correlation_id=f"collection-run:{run_id}",
    )


def append_event_ndjson(*, output_path: Path, event: JobCollectedV1) -> None:
    LocalNdjsonEventBus(output_path).publish(event)


async def run_collector_worker_once(
    *,
    output_path: Path,
    settings: Settings | None = None,
    event_bus: EventBusPort | None = None,
) -> str:
    runtime_settings = settings or load_settings()
    repository = create_repository(runtime_settings)
    collector = create_collection_service(settings=runtime_settings, repository=repository)
    run = repository.start_collection_run()
    correlation_id = f"collection-run:{run.id}"
    logger.info(
        "collector_worker iniciado run_id=%s correlation_id=%s output=%s",
        run.id,
        correlation_id,
        output_path,
    )
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
        logger.exception(
            "collector_worker falhou run_id=%s correlation_id=%s output=%s",
            run.id,
            correlation_id,
            output_path,
        )
        append_worker_dlq_event(
            output_path=dlq_path,
            event=build_worker_dlq_event(
                worker="collector_worker",
                operation="collect_new_jobs_report",
                payload={"run_id": run.id, "output_path": str(output_path)},
                error=str(exc),
                correlation_id=correlation_id,
            ),
        )
        raise
    event = build_job_collected_event(run_id=run.id, report=report)
    if event_bus is None:
        append_event_ndjson(output_path=output_path, event=event)
    else:
        event_bus.publish(event)
    logger.info(
        "collector_worker publicou evento event_type=%s event_id=%s run_id=%s correlation_id=%s jobs_seen=%s jobs_saved=%s errors=%s",
        event.event_type,
        event.event_id,
        run.id,
        event.correlation_id,
        report.jobs_seen,
        report.jobs_saved,
        report.errors,
    )
    return (
        f"collector_worker: evento JobCollectedV1 emitido "
        f"run_id={run.id} vistas={report.jobs_seen} persistidas={report.jobs_saved} "
        f"arquivo={output_path}"
    )
