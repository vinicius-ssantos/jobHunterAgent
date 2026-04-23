from __future__ import annotations

from job_hunter_agent.application.app import JobHunterApplication
from job_hunter_agent.application.composition import create_repository
from job_hunter_agent.core.settings import load_settings


def create_query_app() -> JobHunterApplication:
    app = _create_cli_app_base()
    app._initialize_query_services()
    return app


def create_review_app() -> JobHunterApplication:
    app = _create_cli_app_base()
    app._initialize_query_services()
    app._initialize_review_services()
    return app


def create_application_flow_app() -> JobHunterApplication:
    app = _create_cli_app_base()
    app._initialize_query_services()
    app._initialize_flow_services()
    return app


def create_auto_apply_app() -> JobHunterApplication:
    app = _create_cli_app_base()
    app._initialize_query_services()
    app._initialize_review_services()
    app._initialize_flow_services()
    return app


def _create_cli_app_base() -> JobHunterApplication:
    app = JobHunterApplication.__new__(JobHunterApplication)
    app.enable_telegram = False
    app.settings = load_settings()
    app.repository = create_repository(app.settings)
    return app
