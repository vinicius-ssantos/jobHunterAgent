from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from job_hunter_agent.application.contracts import ApplicationSubmissionResult
from job_hunter_agent.collectors.linkedin_application_runtime import run_with_linkedin_page
from job_hunter_agent.collectors.linkedin_application_state import (
    LinkedInApplicationPageState,
    describe_linkedin_job_page_readiness,
    describe_linkedin_modal_blocker,
)
from job_hunter_agent.collectors.linkedin_application_submit import evaluate_linkedin_submit_readiness
from job_hunter_agent.core.domain import JobPosting


async def submit_linkedin_application(
    *,
    job: JobPosting,
    storage_state_path: Path,
    headless: bool,
    ensure_target_job_page: Callable[[object, JobPosting], Awaitable[None]],
    read_state_with_hydration: Callable[[object, JobPosting], Awaitable[tuple[LinkedInApplicationPageState, object]]],
    capture_failure_artifacts: Callable[..., Awaitable[str]],
    prepare_submit_state: Callable[[object, LinkedInApplicationPageState], Awaitable[LinkedInApplicationPageState]],
    execution_submit: Callable[[object], Awaitable[bool]],
    format_modal_interpretation_for_error: Callable[[LinkedInApplicationPageState], str],
    build_submit_exception_result: Callable[..., Awaitable[ApplicationSubmissionResult]],
    submitted_at_provider: Callable[[], str],
) -> ApplicationSubmissionResult:
    async def _operate(page) -> ApplicationSubmissionResult:
        state = LinkedInApplicationPageState()
        try:
            await page.goto(job.url, wait_until="domcontentloaded")
            await ensure_target_job_page(page, job)
            state, readiness = await read_state_with_hydration(page, job)
            if readiness.result != "ready":
                artifact_detail = await capture_failure_artifacts(
                    page,
                    state=state,
                    job=job,
                    phase="submit",
                    detail=f"submissao real bloqueada: {describe_linkedin_job_page_readiness(readiness)}",
                )
                return ApplicationSubmissionResult(
                    status="error_submit",
                    detail=f"submissao real bloqueada: {describe_linkedin_job_page_readiness(readiness)}{artifact_detail}",
                )
            if not state.easy_apply:
                return ApplicationSubmissionResult(
                    status="error_submit",
                    detail="submissao real bloqueada: CTA de candidatura simplificada nao encontrado",
                )
            state = await prepare_submit_state(page, state)
            if not state.modal_open or not state.modal_submit_visible:
                submit_readiness = evaluate_linkedin_submit_readiness(
                    state,
                    interpretation_detail=format_modal_interpretation_for_error(state),
                )
                artifact_detail = await capture_failure_artifacts(
                    page,
                    state=state,
                    job=job,
                    phase="submit",
                    detail=(
                        "submissao real bloqueada: fluxo nao chegou ao botao de envio"
                        f" | bloqueio={describe_linkedin_modal_blocker(state)}"
                    ),
                )
                return ApplicationSubmissionResult(
                    status="error_submit",
                    detail=f"{submit_readiness.detail}{artifact_detail}",
                )
            submitted = await execution_submit(page)
            if not submitted:
                artifact_detail = await capture_failure_artifacts(
                    page,
                    state=state,
                    job=job,
                    phase="submit",
                    detail="submissao real falhou: clique final de envio nao confirmou sucesso",
                )
                return ApplicationSubmissionResult(
                    status="error_submit",
                    detail=(
                        "submissao real falhou: clique final de envio nao confirmou sucesso"
                        f"{artifact_detail}"
                    ),
                )
            return ApplicationSubmissionResult(
                status="submitted",
                detail="submissao real concluida no LinkedIn",
                submitted_at=submitted_at_provider(),
            )
        except Exception as exc:
            return await build_submit_exception_result(exc, page=page, state=state, job=job)

    return await run_with_linkedin_page(
        storage_state_path=storage_state_path,
        headless=headless,
        page_operation=_operate,
    )
