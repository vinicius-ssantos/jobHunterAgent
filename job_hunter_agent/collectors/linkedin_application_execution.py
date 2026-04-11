from __future__ import annotations

from typing import Awaitable, Callable

from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


class LinkedInEasyApplyExecution:
    def __init__(
        self,
        *,
        inspect_easy_apply_modal: Callable[[object, LinkedInApplicationPageState, bool], Awaitable[LinkedInApplicationPageState]],
        try_open_easy_apply_modal: Callable[[object], Awaitable[bool]],
        try_open_easy_apply_via_direct_url: Callable[[object, bool], Awaitable[LinkedInApplicationPageState]],
        try_submit_application: Callable[[object], Awaitable[bool]],
        read_page_state: Callable[[object], Awaitable[LinkedInApplicationPageState]],
    ) -> None:
        self._inspect_easy_apply_modal = inspect_easy_apply_modal
        self._try_open_easy_apply_modal = try_open_easy_apply_modal
        self._try_open_easy_apply_via_direct_url = try_open_easy_apply_via_direct_url
        self._try_submit_application = try_submit_application
        self._read_page_state = read_page_state

    async def inspect_preflight_state(
        self,
        page,
        state: LinkedInApplicationPageState,
    ) -> LinkedInApplicationPageState:
        if not state.easy_apply:
            return state
        state = await self._inspect_easy_apply_modal(page, state, True)
        if state.easy_apply and not state.modal_open:
            state = await self._try_open_easy_apply_via_direct_url(page, True)
        return state

    async def prepare_submit_state(
        self,
        page,
        state: LinkedInApplicationPageState,
    ) -> LinkedInApplicationPageState:
        state = await self._inspect_easy_apply_modal(page, state, False)
        if not state.modal_open:
            await self._try_open_easy_apply_modal(page)
            await page.wait_for_timeout(1800)
            state = await self._read_page_state(page)
            if state.modal_open:
                state = await self._inspect_easy_apply_modal(page, state, False)
        if not state.modal_open and state.easy_apply:
            state = await self._try_open_easy_apply_via_direct_url(page, False)
        return state

    async def submit(self, page) -> bool:
        return await self._try_submit_application(page)
