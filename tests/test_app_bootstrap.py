from unittest import TestCase
from unittest.mock import patch

from job_hunter_agent.application.app import JobHunterApplication
from job_hunter_agent.application.cli_bootstrap import (
    create_application_flow_app,
    create_query_app,
    create_review_app,
)


class JobHunterApplicationBootstrapTests(TestCase):
    def test_create_query_app_avoids_runtime_collection_and_notifier(self) -> None:
        settings = object()
        repository = object()

        with patch("job_hunter_agent.application.cli_bootstrap.load_settings", return_value=settings) as load_settings_mock, patch(
            "job_hunter_agent.application.cli_bootstrap.create_repository",
            return_value=repository,
        ) as create_repository_mock, patch.object(
            JobHunterApplication,
            "_initialize_query_services",
        ) as initialize_query_mock, patch.object(
            JobHunterApplication,
            "_initialize_review_services",
        ) as initialize_review_mock, patch.object(
            JobHunterApplication,
            "_initialize_flow_services",
        ) as initialize_flow_mock:
            app = create_query_app()

        load_settings_mock.assert_called_once_with()
        create_repository_mock.assert_called_once_with(settings)
        initialize_query_mock.assert_called_once_with()
        initialize_review_mock.assert_not_called()
        initialize_flow_mock.assert_not_called()
        self.assertIs(app.repository, repository)
        self.assertFalse(app.enable_telegram)

    def test_create_review_app_initializes_review_services_only(self) -> None:
        settings = object()
        repository = object()

        with patch("job_hunter_agent.application.cli_bootstrap.load_settings", return_value=settings), patch(
            "job_hunter_agent.application.cli_bootstrap.create_repository",
            return_value=repository,
        ), patch.object(
            JobHunterApplication,
            "_initialize_query_services",
        ) as initialize_query_mock, patch.object(
            JobHunterApplication,
            "_initialize_review_services",
        ) as initialize_review_mock, patch.object(
            JobHunterApplication,
            "_initialize_flow_services",
        ) as initialize_flow_mock:
            app = create_review_app()

        initialize_query_mock.assert_called_once_with()
        initialize_review_mock.assert_called_once_with()
        initialize_flow_mock.assert_not_called()
        self.assertIs(app.repository, repository)
        self.assertFalse(app.enable_telegram)

    def test_create_application_flow_app_initializes_flow_services_only(self) -> None:
        settings = object()
        repository = object()

        with patch("job_hunter_agent.application.cli_bootstrap.load_settings", return_value=settings), patch(
            "job_hunter_agent.application.cli_bootstrap.create_repository",
            return_value=repository,
        ), patch.object(
            JobHunterApplication,
            "_initialize_query_services",
        ) as initialize_query_mock, patch.object(
            JobHunterApplication,
            "_initialize_review_services",
        ) as initialize_review_mock, patch.object(
            JobHunterApplication,
            "_initialize_flow_services",
        ) as initialize_flow_mock:
            app = create_application_flow_app()

        initialize_query_mock.assert_called_once_with()
        initialize_review_mock.assert_not_called()
        initialize_flow_mock.assert_called_once_with()
        self.assertIs(app.repository, repository)
        self.assertFalse(app.enable_telegram)
