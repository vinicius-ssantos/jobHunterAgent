from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from job_hunter_agent.collectors.linkedin_application_runtime import run_with_linkedin_page
from job_hunter_agent.collectors.linkedin_application_state import (
    LinkedInApplicationInspection,
    LinkedInApplicationPageState,
    describe_linkedin_job_page_readiness,
)
from job_hunter_agent.core.domain import JobPosting


async def inspect_linkedin_application(
    *,
    job: JobPosting,
    storage_state_path: Path,
    headless: bool,
    ensure_target_job_page: Callable[[object, JobPosting], Awaitable[None]],
    read_state_with_hydration: Callable[[object, JobPosting], Awaitable[tuple[LinkedInApplicationPageState, object]]],
    capture_failure_artifacts: Callable[..., Awaitable[str]],
    inspect_preflight_state: Callable[[object, LinkedInApplicationPageState], Awaitable[LinkedInApplicationPageState]],
    classify_page_state: Callable[[LinkedInApplicationPageState], LinkedInApplicationInspection],
    modal_interpretation_formatter: Callable[[LinkedInApplicationPageState], str] | None,
) -> LinkedInApplicationInspection:
    async def _operate(page) -> LinkedInApplicationInspection:
        await page.goto(job.url, wait_until="domcontentloaded")
        await ensure_target_job_page(page, job)
        state, readiness = await read_state_with_hydration(page, job)
        if readiness.result != "ready":
            artifact_detail = await capture_failure_artifacts(
                page,
                state=state,
                job=job,
                phase="preflight",
                detail=f"preflight real bloqueado: {describe_linkedin_job_page_readiness(readiness)}",
            )
            return LinkedInApplicationInspection(
                outcome="blocked",
                detail=f"preflight real bloqueado: {describe_linkedin_job_page_readiness(readiness)}{artifact_detail}",
            )
        state = await inspect_preflight_state(page, state)
        if state.easy_apply and not state.modal_open:
            artifact_detail = await capture_failure_artifacts(
                page,
                state=state,
                job=job,
                phase="preflight",
                detail="preflight real inconclusivo: CTA de candidatura simplificada encontrado, mas modal nao abriu",
            )
        else:
            artifact_detail = ""

        inspection = classify_page_state(state)
        if modal_interpretation_formatter is not None and state.modal_open:
            try:
                extra = modal_interpretation_formatter(state).strip()
            except Exception:
                extra = ""
            if extra:
                inspection = LinkedInApplicationInspection(
                    outcome=inspection.outcome,
                    detail=f"{inspection.detail} | {extra}",
                )
        if artifact_detail:
            inspection = LinkedInApplicationInspection(
                outcome=inspection.outcome,
                detail=f"{inspection.detail}{artifact_detail}",
            )
        return inspection

    return await run_with_linkedin_page(
        storage_state_path=storage_state_path,
        headless=headless,
        page_operation=_operate,
    )
