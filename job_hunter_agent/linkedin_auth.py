from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright

from job_hunter_agent.collector import resolve_local_chromium
from job_hunter_agent.settings import Settings


async def bootstrap_linkedin_storage_state(settings: Settings) -> Path:
    persistent_profile_dir = settings.linkedin_persistent_profile_dir.resolve()
    storage_state_path = settings.linkedin_storage_state_path.resolve()
    persistent_profile_dir.mkdir(parents=True, exist_ok=True)
    storage_state_path.parent.mkdir(parents=True, exist_ok=True)

    executable_path = resolve_local_chromium()
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(persistent_profile_dir),
            executable_path=str(executable_path),
            headless=False,
            args=["--start-maximized"],
        )
        try:
            page = await _resolve_page(context)
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            print(
                "Janela do LinkedIn aberta em um perfil dedicado de bootstrap. "
                "Faca login manualmente se necessario e, quando a sessao estiver logada, pressione Enter neste terminal para exportar o storage_state."
            )
            await asyncio.to_thread(input)
            await context.storage_state(path=str(storage_state_path))
        finally:
            await context.close()

    return storage_state_path


async def _resolve_page(context: BrowserContext) -> Page:
    if context.pages:
        return context.pages[0]
    return await context.new_page()
