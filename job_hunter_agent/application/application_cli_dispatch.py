from __future__ import annotations

import asyncio
from argparse import Namespace

from job_hunter_agent.application.app import suggest_candidate_profile
from job_hunter_agent.application.application_cli import (
    APPLICATION_STATUS_ALIASES,
    JOB_STATUS_ALIASES,
)
from job_hunter_agent.application.collector_worker import run_collector_worker_once
from job_hunter_agent.application.domain_events_cli import render_domain_events
from job_hunter_agent.application.matching_worker import run_matching_worker_once
from job_hunter_agent.application.worker_catalog import render_worker_catalog
from job_hunter_agent.application.cli_bootstrap import (
    create_application_flow_app,
    create_auto_apply_app,
    create_query_app,
    create_review_app,
)
from job_hunter_agent.collectors.linkedin_auth import bootstrap_linkedin_storage_state
from job_hunter_agent.core.settings import load_settings


def execute_cli_command(args: Namespace) -> bool:
    if args.bootstrap_linkedin_session:
        settings = load_settings()
        asyncio.run(bootstrap_linkedin_storage_state(settings))
        return True
    if args.command == "status":
        app = create_query_app()
        print(app.show_status_overview())
        return True
    if args.command == "health":
        app = create_query_app()
        print(app.show_health_report())
        return True
    if args.command == "jobs":
        _run_jobs_command(args)
        return True
    if args.command == "applications":
        _run_applications_command(args)
        return True
    if args.command == "domain-events":
        _run_domain_events_command(args)
        return True
    if args.command == "candidate-profile":
        _run_candidate_profile_command(args)
        return True
    if args.command == "worker":
        _run_worker_command(args)
        return True
    return False


def _run_jobs_command(args: Namespace) -> None:
    if args.jobs_command == "list":
        app = create_query_app()
        status = JOB_STATUS_ALIASES.get(args.status, args.status)
        print(app.list_jobs(status=status))
        return
    if args.jobs_command == "show":
        app = create_query_app()
        print(app.show_job(args.id))
        return
    app = create_review_app()
    if args.jobs_command == "approve":
        print(app.review_job(args.id, "approve"))
        return
    if args.jobs_command == "reject":
        print(app.review_job(args.id, "reject"))


def _run_applications_command(args: Namespace) -> None:
    if args.applications_command == "list":
        app = create_query_app()
        status = APPLICATION_STATUS_ALIASES.get(args.status, args.status)
        print(app.list_applications(status=status))
        return
    if args.applications_command == "show":
        app = create_query_app()
        print(app.show_application(args.id))
        return
    if args.applications_command == "diagnose":
        app = create_query_app()
        print(app.diagnose_application(args.id))
        return
    if args.applications_command == "report":
        app = create_query_app()
        print(
            app.generate_application_report(
                args.id,
                output_path=getattr(args, "output", None),
                force=getattr(args, "force", False),
            )
        )
        return
    if args.applications_command == "events":
        app = create_query_app()
        print(app.show_application_events(args.id, limit=args.limit))
        return
    if args.applications_command == "artifacts":
        app = create_query_app()
        print(app.show_latest_failure_artifacts(limit=args.limit))
        return
    if args.applications_command == "create":
        app = create_review_app()
        print(app.create_application_draft_for_job(args.job_id))
        return
    if args.applications_command == "prepare":
        app = create_review_app()
        print(app.transition_application(args.id, "app_prepare"))
        return
    if args.applications_command == "confirm":
        app = create_review_app()
        print(app.transition_application(args.id, "app_confirm"))
        return
    if args.applications_command == "cancel":
        app = create_review_app()
        print(app.transition_application(args.id, "app_cancel"))
        return
    if args.applications_command == "authorize":
        app = create_review_app()
        print(app.authorize_application(args.id))
        return
    if args.applications_command == "auto-apply":
        app = create_auto_apply_app()
        print(app.run_auto_easy_apply_once())
        return
    app = create_application_flow_app()
    if args.applications_command == "preflight":
        if getattr(args, "dry_run", False):
            print(app.show_application_preflight_dry_run(args.id))
            return
        print(asyncio.run(app.handle_application_preflight(args.id)))
        return
    if args.applications_command == "submit":
        if getattr(args, "dry_run", False):
            print(app.show_application_submit_dry_run(args.id))
            return
        print(asyncio.run(app.handle_application_submit(args.id)))


def _run_domain_events_command(args: Namespace) -> None:
    settings = load_settings()
    path = args.path or settings.domain_events_path
    print(
        render_domain_events(
            path=path,
            limit=args.limit,
            event_type=args.event_type,
            correlation_id=args.correlation_id,
            as_json=args.json,
        )
    )


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


def _run_worker_command(args: Namespace) -> None:
    if args.worker_command == "list":
        print(render_worker_catalog())
        return
    if args.worker_command == "collect":
        print(asyncio.run(run_collector_worker_once(output_path=args.output)))
        return
    if args.worker_command == "match":
        print(
            asyncio.run(
                run_matching_worker_once(
                    input_path=args.input,
                    output_path=args.output,
                    state_path=args.state,
                )
            )
        )
