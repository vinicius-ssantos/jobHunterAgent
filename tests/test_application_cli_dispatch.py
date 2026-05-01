from argparse import Namespace
from pathlib import Path
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

    def test_execute_cli_command_dispatches_operations_report(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "show_operations_report": lambda self, days=None, date=None: f"operations={days}|date={date}",
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="operations",
            operations_command="report",
            days=7,
            date="2026-05-01",
            sem_telegram=True,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_query_app",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        print_mock.assert_called_once_with("operations=7|date=2026-05-01")

    def test_execute_cli_command_dispatches_operations_next_actions(self) -> None:
        fake_repository = object()
        fake_app = type(
            "FakeApp",
            (),
            {
                "repository": fake_repository,
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="operations",
            operations_command="next-actions",
            sem_telegram=True,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_query_app",
            return_value=fake_app,
        ) as app_factory, patch(
            "job_hunter_agent.application.application_cli_dispatch.build_operations_next_actions_from_repository",
            return_value=[],
        ) as build_actions, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        build_actions.assert_called_once_with(fake_repository)
        print_mock.assert_called_once_with("Nenhuma proxima acao operacional encontrada.")

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

    def test_execute_cli_command_dispatches_application_diagnose(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "diagnose_application": lambda self, application_id: f"diagnose={application_id}",
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="applications",
            applications_command="diagnose",
            id=35,
            sem_telegram=False,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_query_app",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        print_mock.assert_called_once_with("diagnose=35")

    def test_execute_cli_command_dispatches_application_report(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "generate_application_report": lambda self, application_id, output_path=None, force=False: (
                    f"report={application_id}|output={output_path}|force={force}"
                ),
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="applications",
            applications_command="report",
            id=35,
            output=None,
            force=False,
            sem_telegram=False,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_query_app",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        print_mock.assert_called_once_with("report=35|output=None|force=False")

    def test_execute_cli_command_dispatches_application_report_output_and_force(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "generate_application_report": lambda self, application_id, output_path=None, force=False: (
                    f"report={application_id}|output={output_path}|force={force}"
                ),
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="applications",
            applications_command="report",
            id=35,
            output=Path("custom/report.md"),
            force=True,
            sem_telegram=False,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_query_app",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        print_mock.assert_called_once_with("report=35|output=custom/report.md|force=True")

    def test_execute_cli_command_dispatches_application_reports_list(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "list_application_reports": lambda self, reports_dir, limit=20: f"reports={reports_dir}|limit={limit}",
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="applications",
            applications_command="reports",
            applications_reports_command="list",
            dir=Path("custom/reports"),
            limit=7,
            sem_telegram=False,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_query_app",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        print_mock.assert_called_once_with("reports=custom/reports|limit=7")

    def test_execute_cli_command_dispatches_application_reports_validate(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "validate_application_reports": lambda self, reports_dir, strict=False: (
                    f"validate={reports_dir}|strict={strict}"
                ),
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="applications",
            applications_command="reports",
            applications_reports_command="validate",
            dir=Path("custom/reports"),
            strict=True,
            sem_telegram=False,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_query_app",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        print_mock.assert_called_once_with("validate=custom/reports|strict=True")

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

    def test_execute_cli_command_dispatches_application_auto_apply(self) -> None:
        fake_app = type(
            "FakeApp",
            (),
            {
                "run_auto_easy_apply_once": lambda self: "auto-apply ok",
            },
        )()

        args = Namespace(
            bootstrap_linkedin_session=False,
            command="applications",
            applications_command="auto-apply",
            sem_telegram=True,
        )

        with patch(
            "job_hunter_agent.application.application_cli_dispatch.create_auto_apply_app",
            return_value=fake_app,
        ) as app_factory, patch("builtins.print") as print_mock:
            handled = execute_cli_command(args)

        self.assertTrue(handled)
        app_factory.assert_called_once_with()
        print_mock.assert_called_once_with("auto-apply ok")

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
