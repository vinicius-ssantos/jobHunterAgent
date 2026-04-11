from __future__ import annotations

from typing import Awaitable, Callable

from job_hunter_agent.collectors.linkedin_application_entrypoint import (
    recover_linkedin_direct_apply_url_from_html,
)
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


class LinkedInApplyHrefEntrypointStrategy:
    def __init__(
        self,
        *,
        extract_easy_apply_href: Callable[[object], Awaitable[str]],
        prepare_job_page_for_apply: Callable[[object], Awaitable[None]],
        read_page_state: Callable[[object], Awaitable[LinkedInApplicationPageState]],
        inspect_easy_apply_modal: Callable[[object, LinkedInApplicationPageState, bool], Awaitable[LinkedInApplicationPageState]],
        is_page_closed: Callable[[object], bool],
    ) -> None:
        self._extract_easy_apply_href = extract_easy_apply_href
        self._prepare_job_page_for_apply = prepare_job_page_for_apply
        self._read_page_state = read_page_state
        self._inspect_easy_apply_modal = inspect_easy_apply_modal
        self._is_page_closed = is_page_closed

    async def open(
        self,
        page,
        *,
        close_modal: bool,
    ) -> LinkedInApplicationPageState:
        direct_apply_url = await self._extract_easy_apply_href(page)
        if not direct_apply_url:
            return await self._read_page_state(page)
        try:
            await page.goto(direct_apply_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1800)
            await self._prepare_job_page_for_apply(page)
            state = await self._read_page_state(page)
            if state.modal_open:
                return await self._inspect_easy_apply_modal(page, state, close_modal)
            return state
        except Exception:
            if self._is_page_closed(page):
                raise
            return await self._read_page_state(page)


class LinkedInApplyHtmlRecoveryStrategy:
    async def recover(
        self,
        page,
        *,
        job_url: str,
    ) -> bool:
        try:
            content = await page.content()
        except Exception:
            return False
        apply_url = recover_linkedin_direct_apply_url_from_html(content, job_url)
        if not apply_url:
            return False
        try:
            await page.goto(apply_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1800)
            return True
        except Exception:
            return False
