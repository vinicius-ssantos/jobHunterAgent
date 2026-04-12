from __future__ import annotations

from typing import Awaitable, Callable, Protocol

from job_hunter_agent.collectors.linkedin_application_entrypoint import (
    recover_linkedin_direct_apply_url_from_html,
)
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


class LinkedInApplyEntrypointStrategy(Protocol):
    async def open(
        self,
        page,
        *,
        initial_state: LinkedInApplicationPageState,
        close_modal: bool,
    ) -> LinkedInApplicationPageState: ...


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
        initial_state: LinkedInApplicationPageState,
        close_modal: bool,
    ) -> LinkedInApplicationPageState:
        direct_apply_url = await self._extract_easy_apply_href(page)
        if not direct_apply_url:
            return initial_state
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


class LinkedInApplyClassicModalStrategy:
    def __init__(
        self,
        *,
        try_open_easy_apply_modal: Callable[[object], Awaitable[bool]],
        read_page_state: Callable[[object], Awaitable[LinkedInApplicationPageState]],
        inspect_open_easy_apply_modal: Callable[[object, LinkedInApplicationPageState, bool], Awaitable[LinkedInApplicationPageState]],
    ) -> None:
        self._try_open_easy_apply_modal = try_open_easy_apply_modal
        self._read_page_state = read_page_state
        self._inspect_open_easy_apply_modal = inspect_open_easy_apply_modal

    async def open(
        self,
        page,
        *,
        initial_state: LinkedInApplicationPageState,
        close_modal: bool,
    ) -> LinkedInApplicationPageState:
        state = initial_state
        opened = False
        for _ in range(2):
            await self._try_open_easy_apply_modal(page)
            await page.wait_for_timeout(2500)
            state = await self._read_page_state(page)
            if state.modal_open:
                opened = True
                break
        if not opened:
            return state
        return await self._inspect_open_easy_apply_modal(page, state, close_modal)


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


class LinkedInApplyEntrypointSequence:
    def __init__(
        self,
        strategies: tuple[LinkedInApplyEntrypointStrategy, ...],
    ) -> None:
        self._strategies = strategies

    async def open(
        self,
        page,
        *,
        initial_state: LinkedInApplicationPageState,
        close_modal: bool,
    ) -> LinkedInApplicationPageState:
        state = initial_state
        if not state.easy_apply:
            return state
        for strategy in self._strategies:
            if state.modal_open:
                return state
            state = await strategy.open(
                page,
                initial_state=state,
                close_modal=close_modal,
            )
        return state
