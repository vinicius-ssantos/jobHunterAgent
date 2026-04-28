from __future__ import annotations

import time
from collections import defaultdict
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
        blocked_by_reason: dict[str, int] = defaultdict(int)

        if not self.settings.auto_easy_apply_enabled:
            return AutoEasyApplyReport(
                analyzed=0,
                submitted=0,
                blocked=0,
                skipped=0,
                consecutive_errors=0,
                details=("auto_easy_apply desabilitado em JOB_HUNTER_AUTO_EASY_APPLY_ENABLED",),
            )
        if not self._is_within_allowed_window(datetime.now()):
            return AutoEasyApplyReport(
                analyzed=0,
                submitted=0,
                blocked=1,
                skipped=0,
                consecutive_errors=0,
                details=(
                    "fora da janela horaria permitida para auto apply",
                ),
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

            submit_result = self.submission.run_for_application(application.id)
            if submit_result.outcome == "submitted":
                submitted += 1
                consecutive_errors = 0
                details.append(f"app_id={application.id} enviada com sucesso")
                if (
                    submitted < self.settings.auto_easy_apply_max_submits_per_cycle
                    and self.settings.auto_easy_apply_cooldown_seconds > 0
                ):
                    time.sleep(self.settings.auto_easy_apply_cooldown_seconds)
                continue

            blocked += 1
            consecutive_errors += 1
            reason_code = f"submit:{submit_result.outcome}"
            blocked_by_reason[reason_code] += 1
            details.append(
                f"app_id={application.id} submit_{submit_result.outcome}={submit_result.detail}"
            )
            if self._should_stop_for_repeated_block(blocked_by_reason):
                details.append(
                    f"parada por bloqueio repetido: {reason_code}={blocked_by_reason[reason_code]}"
                )
                break

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
        for application in self.repository.list_applications_by_status("authorized_submit"):
            job = self.repository.get_job(application.job_id)
            if job is None:
                continue
            ordered.append((application, job))
        ordered.sort(key=lambda item: item[1].relevance, reverse=True)
        return ordered

    def _evaluate_gates(self, *, application: JobApplication, job: JobPosting) -> str | None:
        if application.status != "authorized_submit":
            return "submit_sem_autorizacao_explicita"
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
        company_text = (job.company or "").strip().lower()
        for denied in self.settings.auto_easy_apply_denylist_company_terms:
            if denied and denied in company_text:
                return "empresa_na_denylist"
        url_text = (job.url or "").strip().lower()
        for denied in self.settings.auto_easy_apply_denylist_url_terms:
            if denied and denied in url_text:
                return "url_na_denylist"
        if not _preflight_indicates_easy_apply(application.last_preflight_detail):
            return "preflight_sem_easy_apply_explicito"
        return None

    def _is_within_allowed_window(self, now: datetime) -> bool:
        start_hour = int(self.settings.auto_easy_apply_allowed_start_hour)
        end_hour = int(self.settings.auto_easy_apply_allowed_end_hour)
        current_hour = int(now.hour)
        if start_hour == end_hour:
            return True
        if start_hour < end_hour:
            return start_hour <= current_hour < end_hour
        return current_hour >= start_hour or current_hour < end_hour

    def _should_stop_for_repeated_block(self, blocked_by_reason: dict[str, int]) -> bool:
        limit = int(self.settings.auto_easy_apply_max_blocks_same_reason)
        if limit <= 0:
            return False
        return any(count >= limit for count in blocked_by_reason.values())


def _preflight_indicates_easy_apply(detail: str) -> bool:
    normalized = (detail or "").strip().lower()
    if not normalized:
        return False
    if "pronto_para_envio=sim" in normalized:
        return True
    return "easy apply" in normalized
