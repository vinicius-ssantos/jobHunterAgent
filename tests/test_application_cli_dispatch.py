from argparse import Namespace
from unittest import TestCase
from unittest.mock import Mock, patch

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
            "job_hunter_agent.application.application_cli_dispatch.create_query_app",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
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
            "job_hunter_agent.application.application_cli_dispatch.create_query_app",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        print_mock.assert_called_once_with("status=authorized_submit")

    def test_execute_cli_command_dispatches_application_preflight_with_flow_app(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "handle_application_preflight": lambda self, application_id: f"preflight={application_id}",
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="applications",
            applications_command="preflight",
            id=7,
            sem_telegram=True,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_application_flow_app",
            return_value=fake_app,
        ) as app_factory, patch(
            "job_hunter_agent.application.application_cli_dispatch.asyncio.run",
            side_effect=lambda value: value,
        ) as asyncio_run, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        asyncio_run.assert_called_once_with("preflight=7")
        print_mock.assert_called_once_with("preflight=7")

    def test_execute_cli_command_returns_false_for_scheduler_mode(self) -> None:
        args = Namespace(
            bootstrap_linkedin_session=False,
            command=None,
        )

        handled = execute_cli_command(args)

        self.assertFalse(handled)

    def test_execute_cli_command_dispatches_worker_collect(self) -> None:
        args = Namespace(
            bootstrap_linkedin_session=False,
            command="worker",
            worker_command="collect",
            output="logs/worker-events.ndjson",
        )

        worker_run = Mock(return_value="worker ok")
        with patch(
            "job_hunter_agent.application.application_cli_dispatch.run_collector_worker_once",
            new=worker_run,
        ), patch(
            "job_hunter_agent.application.application_cli_dispatch.asyncio.run",
            return_value="worker ok",
        ) as asyncio_run, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        worker_run.assert_called_once_with(output_path="logs/worker-events.ndjson")
        asyncio_run.assert_called_once()
        print_mock.assert_called_once_with("worker ok")

    def test_execute_cli_command_dispatches_worker_match(self) -> None:
        args = Namespace(
            bootstrap_linkedin_session=False,
            command="worker",
            worker_command="match",
            input="logs/worker-events.ndjson",
            output="logs/worker-scored-events.ndjson",
            state="logs/worker-match-state.json",
        )

        worker_run = Mock(return_value="matching ok")
        with patch(
            "job_hunter_agent.application.application_cli_dispatch.run_matching_worker_once",
            new=worker_run,
        ), patch(
            "job_hunter_agent.application.application_cli_dispatch.asyncio.run",
            return_value="matching ok",
        ) as asyncio_run, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        worker_run.assert_called_once_with(
            input_path="logs/worker-events.ndjson",
            output_path="logs/worker-scored-events.ndjson",
            state_path="logs/worker-match-state.json",
        )
        asyncio_run.assert_called_once()
        print_mock.assert_called_once_with("matching ok")
