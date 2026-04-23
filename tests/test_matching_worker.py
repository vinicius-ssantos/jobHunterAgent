from __future__ import annotations

import json
from unittest import IsolatedAsyncioTestCase

from job_hunter_agent.application.matching_worker import run_matching_worker_once
from tests.tmp_workspace import prepare_workspace_tmp_dir


class MatchingWorkerExecutionTests(IsolatedAsyncioTestCase):
    async def test_run_matching_worker_once_emits_scored_events_and_is_idempotent(self) -> None:
        temp_dir = prepare_workspace_tmp_dir("matching-worker")
        input_path = temp_dir / "collected.ndjson"
        output_path = temp_dir / "scored.ndjson"
        state_path = temp_dir / "state.json"
        input_event = {
            "run_id": 77,
            "jobs_seen": 2,
            "jobs_saved": 2,
            "errors": 0,
            "jobs": [
                {
                    "external_key": "k1",
                    "relevance": 9,
                },
                {
                    "external_key": "k2",
                    "relevance": 3,
                },
            ],
        }
        input_path.write_text(json.dumps(input_event, ensure_ascii=False) + "\n", encoding="utf-8")
        settings = type("Settings", (), {"minimum_relevance": 6})()
        try:
            first = await run_matching_worker_once(
                input_path=input_path,
                output_path=output_path,
                state_path=state_path,
                settings=settings,
            )
            second = await run_matching_worker_once(
                input_path=input_path,
                output_path=output_path,
                state_path=state_path,
                settings=settings,
            )

            scored_lines = output_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(scored_lines), 2)
            first_payload = json.loads(scored_lines[0])
            second_payload = json.loads(scored_lines[1])
            self.assertEqual(first_payload["external_key"], "k1")
            self.assertTrue(first_payload["accepted"])
            self.assertEqual(second_payload["external_key"], "k2")
            self.assertFalse(second_payload["accepted"])

            state_payload = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(state_payload["processed_event_ids"]),
                {"77:k1", "77:k2"},
            )
            self.assertIn("emitidos=2", first)
            self.assertIn("duplicados_ignorados=0", first)
            self.assertIn("emitidos=0", second)
            self.assertIn("duplicados_ignorados=2", second)
        finally:
            for path in (input_path, output_path, state_path):
                if path.exists():
                    path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()
