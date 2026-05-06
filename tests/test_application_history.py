import sqlite3
from unittest import TestCase

from job_hunter_agent.infrastructure.application_history import (
    list_application_artifacts,
    list_application_events,
    record_application_artifact,
    record_application_event,
)
from job_hunter_agent.infrastructure.schema_migrations import ensure_current_schema_version


class ApplicationHistoryTests(TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("CREATE TABLE job_applications (id INTEGER PRIMARY KEY)")
        self.connection.execute("INSERT INTO job_applications (id) VALUES (1)")
        ensure_current_schema_version(self.connection)

    def test_record_and_list_application_event(self) -> None:
        event = record_application_event(
            self.connection,
            application_id=1,
            event_type="status_changed",
            payload={"from_status": "draft", "to_status": "reviewed"},
            occurred_at_utc="2026-01-01T00:00:00+00:00",
        )

        events = list_application_events(self.connection, 1)

        self.assertEqual(1, event.id)
        self.assertEqual([event], events)
        self.assertEqual("status_changed", events[0].event_type)
        self.assertEqual(
            {"from_status": "draft", "to_status": "reviewed"},
            events[0].payload,
        )

    def test_record_and_list_application_artifact(self) -> None:
        artifact = record_application_artifact(
            self.connection,
            application_id=1,
            artifact_type="preflight_report",
            path="artifacts/preflight.txt",
            metadata={"source": "linkedin"},
            created_at_utc="2026-01-01T00:00:00+00:00",
        )

        artifacts = list_application_artifacts(self.connection, 1)

        self.assertEqual(1, artifact.id)
        self.assertEqual([artifact], artifacts)
        self.assertEqual("preflight_report", artifacts[0].artifact_type)
        self.assertEqual("artifacts/preflight.txt", artifacts[0].path)
        self.assertEqual({"source": "linkedin"}, artifacts[0].metadata)
