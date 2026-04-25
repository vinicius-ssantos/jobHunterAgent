from __future__ import annotations

import json
from pathlib import Path

from job_hunter_agent.application.worker_runtime import (
    DEFAULT_WORKER_DLQ_PATH,
    append_worker_dlq_event,
    build_worker_dlq_event,
    run_with_retry,
)
from job_hunter_agent.core.event_bus import EventBusPort, LocalNdjsonEventBus
from job_hunter_agent.core.events import JobCollectedV1, JobScoredV1
from job_hunter_agent.core.idempotency import build_job_scoring_key
from job_hunter_agent.core.settings import Settings, load_settings


def append_scored_event_ndjson(*, output_path: Path, event: JobScoredV1) -> None:
    LocalNdjsonEventBus(output_path).publish(event)


def load_processed_event_ids(*, state_path: Path) -> set[str]:
    if not state_path.exists():
        return set()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    if not isinstance(payload, dict):
        return set()
    raw_ids = payload.get("processed_event_ids")
    if not isinstance(raw_ids, list):
        return set()
    return {str(item) for item in raw_ids if isinstance(item, str)}


def save_processed_event_ids(*, state_path: Path, processed_event_ids: set[str]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "processed_event_ids": sorted(processed_event_ids),
    }
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _iter_collected_events(*, input_path: Path) -> list[JobCollectedV1]:
    return list(LocalNdjsonEventBus(input_path).read_job_collected())


async def run_matching_worker_once(
    *,
    input_path: Path,
    output_path: Path,
    state_path: Path,
    settings: Settings | None = None,
    input_bus: EventBusPort | None = None,
    output_bus: EventBusPort | None = None,
) -> str:
    runtime_settings = settings or load_settings()
    dlq_path = DEFAULT_WORKER_DLQ_PATH

    async def _process() -> tuple[int, int]:
        processed_ids = load_processed_event_ids(state_path=state_path)
        source_bus = input_bus or LocalNdjsonEventBus(input_path)
        sink_bus = output_bus or LocalNdjsonEventBus(output_path)
        events = tuple(event for event in source_bus.read_all() if isinstance(event, JobCollectedV1))
        emitted_count = 0
        skipped_duplicates = 0

        for event in events:
            if event.run_id <= 0:
                continue
            for job in event.jobs:
                external_key = str(job.external_key or "").strip()
                if not external_key:
                    continue
                event_key = build_job_scoring_key(event=event, external_key=external_key)
                if event_key in processed_ids:
                    skipped_duplicates += 1
                    continue
                scored_event = JobScoredV1(
                    run_id=event.run_id,
                    external_key=external_key,
                    accepted=job.relevance >= runtime_settings.minimum_relevance,
                    relevance=job.relevance,
                    correlation_id=event.correlation_id or event.event_id,
                )
                sink_bus.publish(scored_event)
                processed_ids.add(event_key)
                emitted_count += 1

        save_processed_event_ids(state_path=state_path, processed_event_ids=processed_ids)
        return emitted_count, skipped_duplicates

    try:
        emitted_count, skipped_duplicates = await run_with_retry(
            operation="matching.process_events",
            action=_process,
        )
    except Exception as exc:
        append_worker_dlq_event(
            output_path=dlq_path,
            event=build_worker_dlq_event(
                worker="matching_worker",
                operation="process_events",
                payload={
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "state_path": str(state_path),
                },
                error=str(exc),
            ),
        )
        raise

    return (
        f"matching_worker: eventos JobScoredV1 emitidos={emitted_count} "
        f"duplicados_ignorados={skipped_duplicates} input={input_path} output={output_path}"
    )
