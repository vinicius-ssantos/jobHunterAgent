from __future__ import annotations

import asyncio
from argparse import Namespace

from job_hunter_agent.application.app import JobHunterApplication, suggest_candidate_profile
from job_hunter_agent.application.application_cli import (
    APPLICATION_STATUS_ALIASES,
    JOB_STATUS_ALIASES,
)
from job_hunter_agent.collectors.linkedin_auth import bootstrap_linkedin_storage_state
from job_hunter_agent.core.settings import load_settings


def execute_cli_command(args: Namespace) -> bool:
    if args.bootstrap_linkedin_session:
        settings = load_settings()
        asyncio.run(bootstrap_linkedin_storage_state(settings))
        return True
    if args.command == "status":
        app = JobHunterApplication(enable_telegram=not args.sem_telegram)
        print(app.show_status_overview())
        return True
    if args.command == "jobs":
        _run_jobs_command(args)
        return True
    if args.command == "applications":
        _run_applications_command(args)
        return True
    if args.command == "candidate-profile":
        _run_candidate_profile_command(args)
        return True
    return False


def _run_jobs_command(args: Namespace) -> None:
    app = JobHunterApplication(enable_telegram=not args.sem_telegram)
    if args.jobs_command == "list":
        status = JOB_STATUS_ALIASES.get(args.status, args.status)
        print(app.list_jobs(status=status))
        return
    if args.jobs_command == "show":
        print(app.show_job(args.id))
        return
    if args.jobs_command == "approve":
        print(app.review_job(args.id, "approve"))
        return
    if args.jobs_command == "reject":
        print(app.review_job(args.id, "reject"))


def _run_applications_command(args: Namespace) -> None:
    app = JobHunterApplication(enable_telegram=not args.sem_telegram)
    if args.applications_command == "list":
        status = APPLICATION_STATUS_ALIASES.get(args.status, args.status)
        print(app.list_applications(status=status))
        return
    if args.applications_command == "create":
        print(app.create_application_draft_for_job(args.job_id))
        return
    if args.applications_command == "show":
        print(app.show_application(args.id))
        return
    if args.applications_command == "events":
        print(app.show_application_events(args.id, limit=args.limit))
        return
    if args.applications_command == "prepare":
        print(app.transition_application(args.id, "app_prepare"))
        return
    if args.applications_command == "confirm":
        print(app.transition_application(args.id, "app_confirm"))
        return
    if args.applications_command == "cancel":
        print(app.transition_application(args.id, "app_cancel"))
        return
    if args.applications_command == "artifacts":
        print(app.show_latest_failure_artifacts(limit=args.limit))
        return
    if args.applications_command == "authorize":
        print(app.authorize_application(args.id))
        return
    if args.applications_command == "preflight":
        print(asyncio.run(app.handle_application_preflight(args.id)))
        return
    if args.applications_command == "submit":
        print(asyncio.run(app.handle_application_submit(args.id)))


def _run_candidate_profile_command(args: Namespace) -> None:
    settings = load_settings()
    if args.candidate_profile_command == "suggest":
        resume_path = args.resume_path or settings.resume_path
        output_path = args.output or settings.candidate_profile_path
        print(
            suggest_candidate_profile(
                resume_path=resume_path,
                output_path=output_path,
                model_name=settings.ollama_model,
                base_url=settings.ollama_url,
            )
        )
