from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from job_hunter_agent.application.cycle_workers import JobScoredV1
from job_hunter_agent.core.settings import Settings, load_settings


def append_scored_event_ndjson(*, output_path: Path, event: JobScoredV1) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(event), ensure_ascii=False, separators=(",", ":"))
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(payload)
        handle.write("\n")


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


def _iter_collected_events(*, input_path: Path) -> list[dict]:
    if not input_path.exists():
        return []
    events: list[dict] = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def _safe_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 0
    return 0


async def run_matching_worker_once(
    *,
    input_path: Path,
    output_path: Path,
    state_path: Path,
    settings: Settings | None = None,
) -> str:
    runtime_settings = settings or load_settings()
    processed_ids = load_processed_event_ids(state_path=state_path)
    events = _iter_collected_events(input_path=input_path)
    emitted_count = 0
    skipped_duplicates = 0

    for event in events:
        run_id = _safe_int(event.get("run_id"))
        jobs = event.get("jobs")
        if run_id <= 0 or not isinstance(jobs, list):
            continue
        for job in jobs:
            if not isinstance(job, dict):
                continue
            external_key = str(job.get("external_key") or "").strip()
            if not external_key:
                continue
            event_key = f"{run_id}:{external_key}"
            if event_key in processed_ids:
                skipped_duplicates += 1
                continue
            relevance = _safe_int(job.get("relevance"))
            scored_event = JobScoredV1(
                run_id=run_id,
                external_key=external_key,
                accepted=relevance >= runtime_settings.minimum_relevance,
                relevance=relevance,
            )
            append_scored_event_ndjson(output_path=output_path, event=scored_event)
            processed_ids.add(event_key)
            emitted_count += 1

    save_processed_event_ids(state_path=state_path, processed_event_ids=processed_ids)
    return (
        f"matching_worker: eventos JobScoredV1 emitidos={emitted_count} "
        f"duplicados_ignorados={skipped_duplicates} input={input_path} output={output_path}"
    )
