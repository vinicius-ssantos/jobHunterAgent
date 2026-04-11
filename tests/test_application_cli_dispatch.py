from argparse import Namespace
from unittest import TestCase
from unittest.mock import patch

from job_hunter_agent.application.application_cli_dispatch import execute_cli_command


class ApplicationCliDispatchTests(TestCase):
    def test_execute_cli_command_dispatches_status(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "show_status_overview": lambda self: "resumo",
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="status",
            sem_telegram=True,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.JobHunterApplication",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with(enable_telegram=False)
        print_mock.assert_called_once_with("resumo")

    def test_execute_cli_command_dispatches_application_list_alias(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "list_applications": lambda self, status=None: f"status={status}",
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="applications",
            applications_command="list",
            status="ready",
            sem_telegram=False,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.JobHunterApplication",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with(enable_telegram=True)
        print_mock.assert_called_once_with("status=authorized_submit")

    def test_execute_cli_command_returns_false_for_scheduler_mode(self) -> None:
        args = Namespace(
            bootstrap_linkedin_session=False,
            command=None,
        )

        handled = execute_cli_command(args)

        self.assertFalse(handled)
