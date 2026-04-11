from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

from job_hunter_agent.core.browser_support import load_playwright_storage_state, resolve_local_chromium

T = TypeVar("T")


def run_linkedin_async(coroutine: Awaitable[T]) -> T:
    import asyncio

    return asyncio.run(coroutine)


async def run_with_linkedin_page(
    *,
    storage_state_path: Path,
    headless: bool,
    page_operation: Callable[[object], Awaitable[T]],
) -> T:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Dependencias de candidatura assistida nao estao instaladas. Rode pip install -r requirements.txt."
        ) from exc

    executable_path = resolve_local_chromium()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=str(executable_path),
            headless=headless,
            args=["--start-maximized"],
        )
        context = await browser.new_context(storage_state=load_playwright_storage_state(storage_state_path))
        page = await context.new_page()
        try:
            return await page_operation(page)
        finally:
            await context.close()
            await browser.close()
