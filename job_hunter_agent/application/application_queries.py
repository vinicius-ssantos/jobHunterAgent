from __future__ import annotations

from pathlib import Path

from job_hunter_agent.application.application_cli_rendering import (
    render_application_detail,
    render_application_diagnosis,
    render_application_events,
    render_application_list,
    render_execution_summary,
    render_failure_artifacts,
    render_job_detail,
    render_job_list,
    render_status_overview,
    summarize_operational_counts,
)
from job_hunter_agent.application.application_report import write_application_report
from job_hunter_agent.core.domain import VALID_APPLICATION_STATUSES, VALID_STATUSES
from job_hunter_agent.core.event_bus import EventBusPort
from job_hunter_agent.infrastructure.repository import JobRepository


APPLICATION_STATUS_ORDER = (
    "draft",
    "ready_for_review",
    "confirmed",
    "authorized_submit",
    "submitted",
    "error_submit",
    "cancelled",
)

JOB_STATUS_ORDER = ("collected", "approved", "rejected", "error_collect")


class ApplicationQueryService:
    def __init__(self, repository: JobRepository, domain_event_bus: EventBusPort | None = None) -> None:
        self.repository = repository
        self.domain_event_bus = domain_event_bus

    def list_applications(self, *, status: str | None = None) -> str:
        requested_statuses = (
            (status,)
            if status is not None
            else tuple(current for current in APPLICATION_STATUS_ORDER if current in VALID_APPLICATION_STATUSES)
        )
        applications_with_jobs: list[tuple[object, object | None]] = []
        list_with_jobs = getattr(self.repository, "list_applications_with_jobs_by_status", None)
        for current_status in requested_statuses:
            if list_with_jobs is not None:
                applications_with_jobs.extend(list_with_jobs(current_status))
                continue
            applications = self.repository.list_applications_by_status(current_status)
            for application in applications:
                applications_with_jobs.append((application, self.repository.get_job(application.job_id)))
        return render_application_list(
            applications_with_jobs=applications_with_jobs,
            status=status,
        )

    def list_jobs(self, *, status: str | None = None) -> str:
        requested_statuses = (
            (status,)
            if status is not None
            else tuple(current for current in JOB_STATUS_ORDER if current in VALID_STATUSES)
        )
        jobs: list[object] = []
        for current_status in requested_statuses:
            jobs.extend(self.repository.list_jobs_by_status(current_status))
        return render_job_list(jobs=jobs, status=status)

    def show_job(self, job_id: int) -> str:
        job = self.repository.get_job(job_id)
        if job is None:
            return f"Vaga nao encontrada: id={job_id}"
        application = self.repository.get_application_by_job(job_id)
        events = self.repository.list_job_events(job_id, limit=5)
        return render_job_detail(job=job, application=application, events=events)

    def show_status_overview(self) -> str:
        job_summary = self.repository.summary()
        application_summary = self.repository.application_summary()
        tracked_applications = self._list_tracked_applications()
        operational_counts = summarize_operational_counts(applications=tracked_applications)
        return render_status_overview(
            job_summary=job_summary,
            application_summary=application_summary,
            operational_counts=operational_counts,
        )

    def show_application_events(self, application_id: int, *, limit: int = 10) -> str:
        application = self.repository.get_application(application_id)
        if application is None:
            return f"Candidatura nao encontrada: id={application_id}"
        events = self.repository.list_application_events(application_id, limit=limit)
        return render_application_events(application_id=application_id, events=events)

    def show_application(self, application_id: int) -> str:
        application = self.repository.get_application(application_id)
        if application is None:
            return f"Candidatura nao encontrada: id={application_id}"
        job = self.repository.get_job(application.job_id)
        events = self.repository.list_application_events(application_id, limit=5)
        return render_application_detail(application=application, job=job, events=events)

    def diagnose_application(self, application_id: int) -> str:
        application = self.repository.get_application(application_id)
        if application is None:
            return f"Candidatura nao encontrada: id={application_id}"
        job = self.repository.get_job(application.job_id)
        events = self.repository.list_application_events(application_id, limit=10)
        correlation_id = f"application:{application_id}"
        domain_events = ()
        if self.domain_event_bus is not None:
            domain_events = tuple(
                event for event in self.domain_event_bus.read_all() if event.correlation_id == correlation_id
            )[-10:]
        return render_application_diagnosis(
            application=application,
            job=job,
            events=events,
            domain_events=domain_events,
            domain_events_enabled=self.domain_event_bus is not None,
        )

    def generate_application_report(self, application_id: int) -> str:
        application = self.repository.get_application(application_id)
        if application is None:
            return f"Candidatura nao encontrada: id={application_id}"
        job = self.repository.get_job(application.job_id)
        if job is None:
            return f"Vaga associada nao encontrada: application_id={application_id} job_id={application.job_id}"
        events = self.repository.list_application_events(application_id, limit=10)
        report_path = write_application_report(
            application=application,
            job=job,
            events=events,
        )
        return f"Relatorio gerado: {report_path}"

    def show_latest_failure_artifacts(self, *, artifacts_dir: Path, limit: int = 5) -> str:
        files = sorted(
            artifacts_dir.glob("*_meta.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return render_failure_artifacts(
            artifacts_dir=artifacts_dir,
            files=files,
            limit=limit,
        )

    def build_execution_summary(self, since: str) -> str:
        list_events_since = getattr(self.repository, "list_recent_application_events_since", None)
        if list_events_since is None:
            return "Execucao operacional:\n- preflights_concluidos=0\n- submits_concluidos=0\n- bloqueios_por_tipo=nenhum"
        events = list_events_since(since)
        return render_execution_summary(events=events)

    def _list_tracked_applications(self) -> list[object]:
        list_tracked = getattr(self.repository, "list_tracked_applications_with_jobs", None)
        if list_tracked is not None:
            return [application for application, _job in list_tracked()]
        tracked_statuses = ("draft", "ready_for_review", "confirmed", "authorized_submit", "error_submit", "submitted")
        applications: list[object] = []
        for status in tracked_statuses:
            applications.extend(self.repository.list_applications_by_status(status))
        return applications
