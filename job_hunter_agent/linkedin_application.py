from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from job_hunter_agent.browser_support import load_playwright_storage_state, resolve_local_chromium
from job_hunter_agent.domain import JobPosting


@dataclass(frozen=True)
class LinkedInApplicationInspection:
    outcome: str
    detail: str


class LinkedInApplicationFlowInspector:
    def __init__(self, *, storage_state_path: str | Path, headless: bool) -> None:
        self.storage_state_path = Path(storage_state_path).resolve()
        self.headless = headless

    def inspect(self, job: JobPosting) -> LinkedInApplicationInspection:
        if "linkedin.com/jobs/" not in job.url.lower():
            return LinkedInApplicationInspection(
                outcome="ignored",
                detail="vaga nao pertence ao fluxo interno do LinkedIn",
            )
        if not self.storage_state_path.exists():
            return LinkedInApplicationInspection(
                outcome="error",
                detail="sessao autenticada do LinkedIn nao encontrada para inspecao real",
            )
        return self._inspect_sync(job)

    def _inspect_sync(self, job: JobPosting) -> LinkedInApplicationInspection:
        import asyncio

        return asyncio.run(self._inspect_async(job))

    async def _inspect_async(self, job: JobPosting) -> LinkedInApplicationInspection:
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
                headless=self.headless,
                args=["--start-maximized"],
            )
            context = await browser.new_context(storage_state=load_playwright_storage_state(self.storage_state_path))
            page = await context.new_page()
            try:
                await page.goto(job.url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)
                state = await page.evaluate(
                    """
                    () => {
                      const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
                      const texts = Array.from(document.querySelectorAll("button, a"))
                        .map((node) => normalize(node.textContent))
                        .filter(Boolean);
                      const joined = texts.join(" | ");
                      const easyApply = texts.some((text) => text.includes("easy apply") || text.includes("candidatura simplificada"));
                      const externalApply = texts.some((text) => text.includes("candidate-se") || text.includes("apply on company website"));
                      const submitVisible = texts.some((text) => text.includes("enviar candidatura") || text.includes("submit application"));
                      return {
                        easyApply,
                        externalApply,
                        submitVisible,
                        sample: joined.slice(0, 400),
                      };
                    }
                    """
                )
            finally:
                await context.close()
                await browser.close()

        if state.get("easyApply"):
            return LinkedInApplicationInspection(
                outcome="ready",
                detail="preflight real ok: CTA de candidatura simplificada encontrado na pagina do LinkedIn",
            )
        if state.get("externalApply"):
            return LinkedInApplicationInspection(
                outcome="blocked",
                detail="preflight real bloqueado: vaga redireciona para candidatura externa",
            )
        if state.get("submitVisible"):
            return LinkedInApplicationInspection(
                outcome="manual_review",
                detail="preflight real inconclusivo: pagina interna com CTA de envio sem fluxo simples claro",
            )
        return LinkedInApplicationInspection(
            outcome="blocked",
            detail="preflight real bloqueado: CTA de candidatura nao encontrado na pagina do LinkedIn",
        )
