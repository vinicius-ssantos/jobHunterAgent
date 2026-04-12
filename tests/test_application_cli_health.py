from __future__ import annotations

from argparse import Namespace
from unittest import TestCase
from unittest.mock import patch

from job_hunter_agent.application.application_cli import parse_args
from job_hunter_agent.application.application_cli_dispatch import execute_cli_command


class ApplicationCliHealthTests(TestCase):
    def test_parse_args_accepts_health_command(self) -> None:
        with patch("sys.argv", ["main.py", "health"]):
            args = parse_args()

        self.assertEqual(args.command, "health")

    def test_execute_cli_command_dispatches_health(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "show_health_report": lambda self: "Health operacional: ok",
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="health",
            sem_telegram=True,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_query_app",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        print_mock.assert_called_once_with("Health operacional: ok")
