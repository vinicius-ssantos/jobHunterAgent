from __future__ import annotations

from typing import Awaitable, Callable

from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


class LinkedInEasyApplyExecution:
    def __init__(
        self,
        *,
        inspect_easy_apply_modal: Callable[[object, LinkedInApplicationPageState, bool], Awaitable[LinkedInApplicationPageState]],
        try_submit_application: Callable[[object], Awaitable[bool]],
    ) -> None:
        self._inspect_easy_apply_modal = inspect_easy_apply_modal
        self._try_submit_application = try_submit_application

    async def inspect_preflight_state(
        self,
        page,
        state: LinkedInApplicationPageState,
    ) -> LinkedInApplicationPageState:
        if not state.easy_apply:
            return state
        return await self._inspect_easy_apply_modal(page, state, True)

    async def prepare_submit_state(
        self,
        page,
        state: LinkedInApplicationPageState,
    ) -> LinkedInApplicationPageState:
        if not state.easy_apply:
            return state
        return await self._inspect_easy_apply_modal(page, state, False)

    async def submit(self, page) -> bool:
        return await self._try_submit_application(page)
