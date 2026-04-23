from __future__ import annotations

import json
from unittest import IsolatedAsyncioTestCase, TestCase

from job_hunter_agent.application.worker_runtime import (
    append_worker_dlq_event,
    build_worker_dlq_event,
    run_with_retry,
)
from tests.tmp_workspace import prepare_workspace_tmp_dir


class WorkerRuntimeRetryTests(IsolatedAsyncioTestCase):
    async def test_run_with_retry_retries_with_backoff_and_succeeds(self) -> None:
        attempts: list[int] = []
        sleeps: list[float] = []

        async def action() -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("falha temporaria")
            return "ok"

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        result = await run_with_retry(
            operation="teste",
            action=action,
            max_attempts=3,
            base_delay_seconds=0.5,
            sleep=fake_sleep,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(len(attempts), 3)
        self.assertEqual(sleeps, [0.5, 1.0])


class WorkerRuntimeDlqTests(TestCase):
    def test_append_worker_dlq_event_writes_ndjson_line(self) -> None:
        temp_dir = prepare_workspace_tmp_dir("worker-dlq")
        output_path = temp_dir / "worker-dlq.ndjson"
        event = build_worker_dlq_event(
            worker="matching_worker",
            operation="process_events",
            payload={"run_id": 1},
            error="erro",
        )
        try:
            append_worker_dlq_event(output_path=output_path, event=event)
            lines = output_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["worker"], "matching_worker")
            self.assertEqual(payload["operation"], "process_events")
            self.assertEqual(payload["payload"], {"run_id": 1})
            self.assertEqual(payload["error"], "erro")
            self.assertIn("+00:00", payload["timestamp_utc"])
        finally:
            if output_path.exists():
                output_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()
