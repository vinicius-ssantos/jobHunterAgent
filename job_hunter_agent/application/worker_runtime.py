from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


DEFAULT_WORKER_MAX_ATTEMPTS = 3
DEFAULT_WORKER_RETRY_BASE_SECONDS = 1.0
DEFAULT_WORKER_DLQ_PATH = Path("logs/worker-dlq.ndjson")


@dataclass(frozen=True)
class WorkerDlqEvent:
    timestamp_utc: str
    worker: str
    operation: str
    payload: dict
    error: str
    correlation_id: str = ""


def append_worker_dlq_event(*, output_path: Path, event: WorkerDlqEvent) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(asdict(event), ensure_ascii=False, separators=(",", ":"))
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(serialized)
        handle.write("\n")


async def run_with_retry(
    *,
    operation: str,
    action: Callable[[], Awaitable[T]],
    max_attempts: int = DEFAULT_WORKER_MAX_ATTEMPTS,
    base_delay_seconds: float = DEFAULT_WORKER_RETRY_BASE_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    if max_attempts <= 0:
        max_attempts = 1
    if base_delay_seconds <= 0:
        base_delay_seconds = 0.1

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await action()
        except Exception as exc:  # pragma: no cover - loop behavior covered by tests
            last_exc = exc
            if attempt >= max_attempts:
                break
            delay = base_delay_seconds * (2 ** (attempt - 1))
            await sleep(delay)
    assert last_exc is not None
    raise RuntimeError(f"{operation} falhou apos {max_attempts} tentativas: {last_exc}") from last_exc


def build_worker_dlq_event(
    *,
    worker: str,
    operation: str,
    payload: dict,
    error: str,
    correlation_id: str = "",
) -> WorkerDlqEvent:
    return WorkerDlqEvent(
        timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        worker=worker,
        operation=operation,
        payload=payload,
        error=error,
        correlation_id=correlation_id,
    )
