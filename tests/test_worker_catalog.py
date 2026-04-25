from __future__ import annotations

import sys
from unittest import TestCase
from unittest.mock import patch

from job_hunter_agent.application.application_cli import parse_args
from job_hunter_agent.application.worker_catalog import (
    list_worker_definitions,
    render_worker_catalog,
)


class WorkerCatalogTests(TestCase):
    def test_catalog_lists_expected_workers(self) -> None:
        workers = list_worker_definitions()
        names = {worker.name for worker in workers}

        self.assertIn("collector-worker", names)
        self.assertIn("matching-worker", names)
        self.assertIn("review-notifier-worker", names)
        self.assertIn("application-worker", names)
        self.assertIn("scheduler-worker", names)

    def test_catalog_marks_heavy_dependencies_explicitly(self) -> None:
        workers = {worker.name: worker for worker in list_worker_definitions()}

        self.assertTrue(workers["collector-worker"].initializes_browser)
        self.assertTrue(workers["collector-worker"].initializes_llm)
        self.assertFalse(workers["collector-worker"].initializes_telegram)
        self.assertFalse(workers["matching-worker"].initializes_browser)
        self.assertFalse(workers["matching-worker"].initializes_telegram)
        self.assertFalse(workers["matching-worker"].initializes_llm)

    def test_render_worker_catalog_includes_commands_and_events(self) -> None:
        rendered = render_worker_catalog()

        self.assertIn("collector-worker", rendered)
        self.assertIn("python main.py worker collect", rendered)
        self.assertIn("JobCollectedV1", rendered)
        self.assertIn("matching-worker", rendered)
        self.assertIn("python main.py worker match", rendered)
        self.assertIn("JobScoredV1", rendered)

    def test_worker_list_parse_args(self) -> None:
        with patch("sys.argv", ["main.py", "worker", "list"]):
            args = parse_args()

        self.assertEqual(args.command, "worker")
        self.assertEqual(args.worker_command, "list")

    def test_importing_worker_catalog_does_not_import_heavy_runtime_modules(self) -> None:
        heavy_modules = (
            "job_hunter_agent.collectors.linkedin",
            "job_hunter_agent.infrastructure.notifier",
            "job_hunter_agent.llm.scoring",
        )
        for module_name in heavy_modules:
            sys.modules.pop(module_name, None)

        __import__("job_hunter_agent.application.worker_catalog")

        for module_name in heavy_modules:
            self.assertNotIn(module_name, sys.modules)
