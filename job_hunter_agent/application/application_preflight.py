from __future__ import annotations

from dataclasses import dataclass

from job_hunter_agent.application.application_flow import (
    ApplicationFlowCoordinator,
    load_application_context,
)
from job_hunter_agent.application.application_messages import (
    format_linkedin_preflight_ready,
    format_preflight_dry_run_ready,
    format_preflight_inspection_error,
    format_preflight_portal_not_supported,
    format_preflight_readiness_incomplete,
    format_preflight_requires_confirmed_status,
    format_preflight_unsupported_flow_blocked,
)
from job_hunter_agent.application.application_ports import (
    InspectionPort,
    normalize_application_flow_inspection,
)
from job_hunter_agent.application.application_readiness import ApplicationReadinessCheckService
from job_hunter_agent.core.portal_capabilities import get_portal_capabilities
from job_hunter_agent.infrastructure.repository import JobRepository


@dataclass(frozen=True)
class ApplicationPreflightResult:
    outcome: str
    detail: str
    application_status: str


class ApplicationPreflightService:
    def __init__(
        self,
        repository: JobRepository,
        flow_inspector: InspectionPort | None = None,
        readiness_checker: ApplicationReadinessCheckService | None = None,
    ) -> None:
        self.repository = repository
        self.flow_inspector = flow_inspector
        self.flow = ApplicationFlowCoordinator(repository)
        self.readiness_checker = readiness_checker

    def run_dry_run_for_application(self, application_id: int) -> ApplicationPreflightResult:
        context = load_application_context(self.repository, application_id)
        application = context.application
        job = context.job

        if application.status != "confirmed":
            return ApplicationPreflightResult(
                outcome="ignored",
                detail=format_preflight_requires_confirmed_status(),
                application_status=application.status,
            )

        if application.support_level == "unsupported":
            return ApplicationPreflightResult(
                outcome="blocked",
                detail=format_preflight_unsupported_flow_blocked(),
                application_status=application.status,
            )

        capabilities = get_portal_capabilities(job)
        if self.readiness_checker is not None:
            readiness = self.readiness_checker.check_preflight_ready(job)
            if not readiness.ok:
                return ApplicationPreflightResult(
                    outcome="blocked",
                    detail=format_preflight_readiness_incomplete(failures=list(readiness.failures)),
                    application_status=application.status,
                )

        if capabilities.preflight_supported and job.source_site.lower() == "linkedin" and "linkedin.com/jobs/" in job.url.lower():
            return ApplicationPreflightResult(
                outcome="ready",
                detail=format_preflight_dry_run_ready(support_level=application.support_level),
                application_status=application.status,
            )

        return ApplicationPreflightResult(
            outcome="blocked",
            detail=format_preflight_portal_not_supported(portal_name=capabilities.portal_name),
            application_status=application.status,
        )

    def run_for_application(self, application_id: int) -> ApplicationPreflightResult:
        context = load_application_context(self.repository, application_id)
        application = context.application
        job = context.job

        if application.status != "confirmed":
            detail = format_preflight_requires_confirmed_status()
            self.flow.record_event(
                application.id,
                event_type="preflight_ignored",
                detail=detail,
                from_status=application.status,
                to_status=application.status,
            )
            return ApplicationPreflightResult(
                outcome="ignored",
                detail=detail,
                application_status=application.status,
            )

        if application.support_level == "unsupported":
            detail = format_preflight_unsupported_flow_blocked()
            application_status = self.flow.record_preflight_result(
                context,
                outcome="blocked",
                detail=detail,
                event_type="preflight_blocked",
                status="error_submit",
                clear_error=False,
            )
            return ApplicationPreflightResult(
                outcome="blocked",
                detail=detail,
                application_status=application_status,
            )

        capabilities = get_portal_capabilities(job)

        if self.readiness_checker is not None:
            readiness = self.readiness_checker.check_preflight_ready(job)
            if not readiness.ok:
                detail = format_preflight_readiness_incomplete(failures=list(readiness.failures))
                application_status = self.flow.record_preflight_result(
                    context,
                    outcome="blocked",
                    detail=detail,
                    event_type="preflight_blocked",
                    status="error_submit",
                    clear_error=False,
                )
                return ApplicationPreflightResult(
                    outcome="blocked",
                    detail=detail,
                    application_status=application_status,
                )

        if capabilities.preflight_supported and job.source_site.lower() == "linkedin" and "linkedin.com/jobs/" in job.url.lower():
            if self.flow_inspector is not None:
                try:
                    inspection = normalize_application_flow_inspection(self.flow_inspector.inspect(job))
                except Exception as exc:
                    inspection = None
                    detail = format_preflight_inspection_error(exc)
                    application_status = self.flow.record_preflight_result(
                        context,
                        outcome="error",
                        detail=detail,
                        event_type="preflight_error",
                        status="confirmed",
                        clear_error=True,
                    )
                    return ApplicationPreflightResult(
                        outcome="error",
                        detail=detail,
                        application_status=application_status,
                    )
                if inspection is not None:
                    if inspection.outcome == "ready":
                        application_status = self.flow.record_preflight_result(
                            context,
                            outcome="ready",
                            detail=inspection.detail,
                            event_type="preflight_ready",
                            status="confirmed",
                            clear_error=True,
                        )
                        return ApplicationPreflightResult(
                            outcome="ready",
                            detail=inspection.detail,
                            application_status=application_status,
                        )
                    if inspection.outcome == "manual_review":
                        application_status = self.flow.record_preflight_result(
                            context,
                            outcome="manual_review",
                            detail=inspection.detail,
                            event_type="preflight_manual_review",
                            status="confirmed",
                            clear_error=True,
                        )
                        return ApplicationPreflightResult(
                            outcome="manual_review",
                            detail=inspection.detail,
                            application_status=application_status,
                        )
                    detail = inspection.detail
                    application_status = self.flow.record_preflight_result(
                        context,
                        outcome="blocked",
                        detail=detail,
                        event_type="preflight_blocked",
                        status="error_submit",
                        clear_error=False,
                    )
                    return ApplicationPreflightResult(
                        outcome="blocked",
                        detail=detail,
                        application_status=application_status,
                    )
            detail = format_linkedin_preflight_ready(support_level=application.support_level)
            application_status = self.flow.record_preflight_result(
                context,
                outcome="ready",
                detail=detail,
                event_type="preflight_ready",
                status="confirmed",
                clear_error=True,
            )
            return ApplicationPreflightResult(
                outcome="ready",
                detail=detail,
                application_status=application_status,
            )

        detail = format_preflight_portal_not_supported(portal_name=capabilities.portal_name)
        application_status = self.flow.record_preflight_result(
            context,
            outcome="blocked",
            detail=detail,
            event_type="preflight_blocked",
            status="error_submit",
            clear_error=False,
        )
        return ApplicationPreflightResult(
            outcome="blocked",
            detail=detail,
            application_status=application_status,
        )
