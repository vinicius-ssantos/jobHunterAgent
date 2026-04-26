from __future__ import annotations

import shutil
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from job_hunter_agent.application.application_cli import parse_args
from job_hunter_agent.application.domain_events_cli import render_domain_events
from job_hunter_agent.core.event_bus import LocalNdjsonEventBus
from job_hunter_agent.core.events import ApplicationBlockedV1, JobReviewedV1
from tests.tmp_workspace import prepare_workspace_tmp_dir


class DomainEventsCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = prepare_workspace_tmp_dir("domain-events-cli")
        self.events_path = self.temp_dir / "domain-events.ndjson"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_render_domain_events_reports_missing_or_empty_file(self) -> None:
        rendered = render_domain_events(path=self.events_path, limit=10)

        self.assertEqual(rendered, f"Nenhum evento de dominio encontrado em {self.events_path}")

    def test_render_domain_events_lists_recent_events(self) -> None:
        bus = LocalNdjsonEventBus(self.events_path)
        bus.publish(
            JobReviewedV1(
                job_id=10,
                decision="approve",
                status="approved",
                reviewed_by="command",
                event_id="evt-reviewed",
                occurred_at="2026-04-24T12:00:00+00:00",
                correlation_id="job:10",
            )
        )
        bus.publish(
            ApplicationBlockedV1(
                application_id=55,
                job_id=10,
                reason="preflight_not_ready",
                retryable=True,
                event_id="evt-blocked",
                occurred_at="2026-04-24T12:01:00+00:00",
                correlation_id="application:55",
            )
        )

        rendered = render_domain_events(path=self.events_path, limit=1)

        self.assertIn("Eventos de dominio: 1 de 2", rendered)
        self.assertIn("ApplicationBlockedV1", rendered)
        self.assertIn("application_id=55", rendered)
        self.assertIn("reason=preflight_not_ready", rendered)
        self.assertNotIn("JobReviewedV1", rendered)

    def test_parse_args_accepts_domain_events_list_command(self) -> None:
        with patch("sys.argv", ["main.py", "domain-events", "list", "--path", "logs/domain-events.ndjson", "--limit", "5"]):
            args = parse_args()

        self.assertEqual(args.command, "domain-events")
        self.assertEqual(args.domain_events_command, "list")
        self.assertEqual(args.path, Path("logs/domain-events.ndjson"))
        self.assertEqual(args.limit, 5)

    def test_parse_args_rejects_non_positive_domain_events_limit(self) -> None:
        with patch("sys.argv", ["main.py", "domain-events", "list", "--limit", "0"]):
            with self.assertRaises(SystemExit):
                parse_args()
