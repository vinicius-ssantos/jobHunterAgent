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
        await page.wait_for_timeout(2500)
        await self._prepare_job_page_for_apply(page)
        state = await self._read_page_state(page)
        readiness = self._assess_job_page_readiness(job, state)
        if readiness.result != "no_apply_cta":
            return state, readiness
        for delay_ms in (1800, 2800):
            try:
                await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            await page.wait_for_timeout(delay_ms)
            await self._prepare_job_page_for_apply(page)
            state = await self._read_page_state(page)
            readiness = self._assess_job_page_readiness(job, state)
            if readiness.result != "no_apply_cta":
                return state, readiness
        recovered = await self.recover_easy_apply_from_page_html(page, job)
        if recovered:
            await self._prepare_job_page_for_apply(page)
            state = await self._read_page_state(page)
            readiness = self._assess_job_page_readiness(job, state)
        return state, readiness

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
