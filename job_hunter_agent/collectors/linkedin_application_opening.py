from __future__ import annotations

from typing import Awaitable, Callable

from job_hunter_agent.collectors.linkedin_application_entry_strategies import (
    LinkedInApplyHrefEntrypointStrategy,
    LinkedInApplyHtmlRecoveryStrategy,
)
from job_hunter_agent.collectors.linkedin_application_state import (
    LinkedInApplicationPageState,
    LinkedInJobPageReadiness,
)
from job_hunter_agent.core.domain import JobPosting

INITIAL_HYDRATION_DELAY_MS = 2500
RETRY_HYDRATION_DELAYS_MS = (1800, 2800)


class LinkedInEasyApplyFlowOpener:
    def __init__(
        self,
        *,
        prepare_job_page_for_apply: Callable[[object], Awaitable[None]],
        read_page_state: Callable[[object], Awaitable[LinkedInApplicationPageState]],
        assess_job_page_readiness: Callable[[JobPosting, LinkedInApplicationPageState], LinkedInJobPageReadiness],
        href_entrypoint: LinkedInApplyHrefEntrypointStrategy,
        html_recovery: LinkedInApplyHtmlRecoveryStrategy,
    ) -> None:
        self._prepare_job_page_for_apply = prepare_job_page_for_apply
        self._read_page_state = read_page_state
        self._assess_job_page_readiness = assess_job_page_readiness
        self._href_entrypoint = href_entrypoint
        self._html_recovery = html_recovery

    async def read_state_with_hydration(
        self,
        page,
        job: JobPosting,
    ) -> tuple[LinkedInApplicationPageState, LinkedInJobPageReadiness]:
        state, readiness = await self._read_ready_state_after_delay(
            page,
            job,
            INITIAL_HYDRATION_DELAY_MS,
        )
        if readiness.result != "no_apply_cta":
            return state, readiness

        for delay_ms in RETRY_HYDRATION_DELAYS_MS:
            await self._wait_for_rehydration_cycle(page, delay_ms)
            state, readiness = await self._read_ready_state(page, job)
            if readiness.result != "no_apply_cta":
                return state, readiness

        return await self._read_ready_state_after_html_recovery(page, job, state, readiness)

    async def recover_easy_apply_from_page_html(self, page, job: JobPosting) -> bool:
        return await self._html_recovery.recover(page, job_url=job.url)

    async def try_open_easy_apply_via_direct_url(
        self,
        page,
        *,
        close_modal: bool,
    ) -> LinkedInApplicationPageState:
        return await self._href_entrypoint.open(
            page,
            initial_state=LinkedInApplicationPageState(easy_apply=True),
            close_modal=close_modal,
        )

    async def _read_ready_state_after_delay(
        self,
        page,
        job: JobPosting,
        delay_ms: int,
    ) -> tuple[LinkedInApplicationPageState, LinkedInJobPageReadiness]:
        await page.wait_for_timeout(delay_ms)
        return await self._read_ready_state(page, job)

    async def _read_ready_state(
        self,
        page,
        job: JobPosting,
    ) -> tuple[LinkedInApplicationPageState, LinkedInJobPageReadiness]:
        await self._prepare_job_page_for_apply(page)
        state = await self._read_page_state(page)
        readiness = self._assess_job_page_readiness(job, state)
        return state, readiness

    async def _wait_for_rehydration_cycle(self, page, delay_ms: int) -> None:
        try:
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        await page.wait_for_timeout(delay_ms)

    async def _read_ready_state_after_html_recovery(
        self,
        page,
        job: JobPosting,
        fallback_state: LinkedInApplicationPageState,
        fallback_readiness: LinkedInJobPageReadiness,
    ) -> tuple[LinkedInApplicationPageState, LinkedInJobPageReadiness]:
        recovered = await self.recover_easy_apply_from_page_html(page, job)
        if not recovered:
            return fallback_state, fallback_readiness
        return await self._read_ready_state(page, job)
