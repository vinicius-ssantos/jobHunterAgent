from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from job_hunter_agent.application.composition import create_domain_event_bus
from job_hunter_agent.core.event_bus import LocalNdjsonEventBus


class DomainEventBusConfigTests(TestCase):
    def test_create_domain_event_bus_returns_none_when_disabled(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "domain_events_enabled": False,
                "domain_events_path": Path("logs/domain-events.ndjson"),
            },
        )()

        self.assertIsNone(create_domain_event_bus(settings))

    def test_create_domain_event_bus_returns_local_ndjson_bus_when_enabled(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "domain_events_enabled": True,
                "domain_events_path": Path("logs/domain-events.ndjson"),
            },
        )()

        event_bus = create_domain_event_bus(settings)

        self.assertIsInstance(event_bus, LocalNdjsonEventBus)
        self.assertEqual(event_bus.path, Path("logs/domain-events.ndjson"))
