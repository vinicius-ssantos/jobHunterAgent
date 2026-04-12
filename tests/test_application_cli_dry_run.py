from __future__ import annotations

from argparse import Namespace
from unittest import TestCase
from unittest.mock import patch

from job_hunter_agent.application.application_cli import parse_args
from job_hunter_agent.application.application_cli_dispatch import execute_cli_command


class ApplicationCliDryRunTests(TestCase):
    def test_parse_args_accepts_preflight_dry_run(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "preflight", "--id", "7", "--dry-run"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "preflight")
        self.assertTrue(args.dry_run)

    def test_parse_args_accepts_submit_dry_run(self) -> None:
        with patch("sys.argv", ["main.py", "applications", "submit", "--id", "7", "--dry-run"]):
            args = parse_args()

        self.assertEqual(args.command, "applications")
        self.assertEqual(args.applications_command, "submit")
        self.assertTrue(args.dry_run)

    def test_execute_cli_command_dispatches_preflight_dry_run_without_asyncio(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "show_application_preflight_dry_run": lambda self, application_id: f"dry-preflight={application_id}",
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="applications",
            applications_command="preflight",
            id=7,
            dry_run=True,
            sem_telegram=True,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_application_flow_app",
            return_value=fake_app,
        ) as app_factory, patch(
            "job_hunter_agent.application.application_cli_dispatch.asyncio.run"
        ) as asyncio_run, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        asyncio_run.assert_not_called()
        print_mock.assert_called_once_with("dry-preflight=7")

    def test_execute_cli_command_dispatches_submit_dry_run_without_asyncio(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "show_application_submit_dry_run": lambda self, application_id: f"dry-submit={application_id}",
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="applications",
            applications_command="submit",
            id=9,
            dry_run=True,
            sem_telegram=True,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_application_flow_app",
            return_value=fake_app,
        ) as app_factory, patch(
            "job_hunter_agent.application.application_cli_dispatch.asyncio.run"
        ) as asyncio_run, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        asyncio_run.assert_not_called()
        print_mock.assert_called_once_with("dry-submit=9")
