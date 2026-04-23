from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

from job_hunter_agent.application.application_preflight import ApplicationPreflightService
from job_hunter_agent.application.application_submission import ApplicationSubmissionService
from job_hunter_agent.application.application_commands import ApplicationTransitionCommandService
from job_hunter_agent.core.domain import JobApplication, JobPosting
from job_hunter_agent.core.settings import Settings
from job_hunter_agent.infrastructure.repository import JobRepository


@dataclass(frozen=True)
class AutoEasyApplyReport:
    analyzed: int
    submitted: int
    blocked: int
    skipped: int
    consecutive_errors: int
    details: tuple[str, ...]


def render_auto_easy_apply_report(report: AutoEasyApplyReport) -> str:
    lines = [
        "Auto Easy Apply:",
        f"- analisadas={report.analyzed}",
        f"- enviadas={report.submitted}",
        f"- bloqueadas={report.blocked}",
        f"- puladas={report.skipped}",
        f"- erros_consecutivos={report.consecutive_errors}",
    ]
    if report.details:
        lines.append("- detalhes:")
        lines.extend(f"  - {detail}" for detail in report.details)
    return "\n".join(lines)


class AutoEasyApplyService:
    def __init__(
        self,
        *,
        repository: JobRepository,
        preflight: ApplicationPreflightService,
        submission: ApplicationSubmissionService,
        transitions: ApplicationTransitionCommandService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.preflight = preflight
        self.submission = submission
        self.transitions = transitions
        self.settings = settings

    def run_once(self) -> AutoEasyApplyReport:
        details: list[str] = []
        analyzed = 0
        submitted = 0
        blocked = 0
        skipped = 0
        consecutive_errors = 0

        if not self.settings.auto_easy_apply_enabled:
            return AutoEasyApplyReport(
                analyzed=0,
                submitted=0,
                blocked=0,
                skipped=0,
                consecutive_errors=0,
                details=("auto_easy_apply desabilitado em JOB_HUNTER_AUTO_EASY_APPLY_ENABLED",),
            )

        start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
        daily_submitted = self.repository.count_submitted_applications_since(start_of_day)
        if daily_submitted >= self.settings.auto_easy_apply_max_submits_per_day:
            return AutoEasyApplyReport(
                analyzed=0,
                submitted=0,
                blocked=1,
                skipped=0,
                consecutive_errors=0,
                details=(
                    f"limite diario atingido: {daily_submitted}/{self.settings.auto_easy_apply_max_submits_per_day}",
                ),
            )

        candidates = self._load_candidates()
        for application, job in candidates:
            if submitted >= self.settings.auto_easy_apply_max_submits_per_cycle:
                details.append(
                    f"limite por ciclo atingido: {submitted}/{self.settings.auto_easy_apply_max_submits_per_cycle}"
                )
                break
            if daily_submitted + submitted >= self.settings.auto_easy_apply_max_submits_per_day:
                details.append(
                    f"limite diario atingido: {daily_submitted + submitted}/{self.settings.auto_easy_apply_max_submits_per_day}"
                )
                break
            if consecutive_errors >= self.settings.auto_easy_apply_max_consecutive_errors:
                details.append(
                    f"circuit breaker acionado apos {consecutive_errors} erro(s) consecutivo(s)"
                )
                break

            analyzed += 1
            gate_reason = self._evaluate_gates(application=application, job=job)
            if gate_reason is not None:
                skipped += 1
                details.append(f"app_id={application.id} gate={gate_reason}")
                continue

            final_application = application
            if application.status == "confirmed":
                preflight_result = self.preflight.run_for_application(application.id)
                if preflight_result.outcome != "ready":
                    blocked += 1
                    details.append(
                        f"app_id={application.id} preflight_bloqueou={preflight_result.detail}"
                    )
                    consecutive_errors = 0
                    continue
                self.transitions.authorize_application(application.id)
                refreshed = self.repository.get_application(application.id)
                if refreshed is None:
                    blocked += 1
                    details.append(f"app_id={application.id} nao encontrada apos autorizar")
                    continue
                final_application = refreshed

            submit_result = self.submission.run_for_application(final_application.id)
            if submit_result.outcome == "submitted":
                submitted += 1
                consecutive_errors = 0
                details.append(f"app_id={final_application.id} enviada com sucesso")
                if (
                    submitted < self.settings.auto_easy_apply_max_submits_per_cycle
                    and self.settings.auto_easy_apply_cooldown_seconds > 0
                ):
                    time.sleep(self.settings.auto_easy_apply_cooldown_seconds)
                continue

            blocked += 1
            consecutive_errors += 1
            details.append(
                f"app_id={final_application.id} submit_{submit_result.outcome}={submit_result.detail}"
            )

        return AutoEasyApplyReport(
            analyzed=analyzed,
            submitted=submitted,
            blocked=blocked,
            skipped=skipped,
            consecutive_errors=consecutive_errors,
            details=tuple(details),
        )

    def _load_candidates(self) -> list[tuple[JobApplication, JobPosting]]:
        ordered: list[tuple[JobApplication, JobPosting]] = []
        for status in ("authorized_submit", "confirmed"):
            for application in self.repository.list_applications_by_status(status):
                job = self.repository.get_job(application.job_id)
                if job is None:
                    continue
                ordered.append((application, job))
        ordered.sort(key=lambda item: item[1].relevance, reverse=True)
        return ordered

    def _evaluate_gates(self, *, application: JobApplication, job: JobPosting) -> str | None:
        if application.status not in {"confirmed", "authorized_submit"}:
            return "status_invalido"
        if job.status != "approved":
            return "vaga_nao_aprovada"
        if job.relevance < self.settings.auto_easy_apply_min_score:
            return "score_abaixo_do_limiar"
        source_site = (job.source_site or "").strip().lower()
        if source_site != "linkedin":
            return "portal_fora_do_alvo"
        if "linkedin.com/jobs/" not in (job.url or "").lower():
            return "url_fora_do_fluxo_linkedin_jobs"
        if application.support_level == "unsupported":
            return "suporte_automatico_indisponivel"
        return None
