from __future__ import annotations

import re

from job_hunter_agent.collectors.linkedin_application_artifacts import is_page_closed


class LinkedInEasyApplyNavigator:
    async def _job_detail_root_selector(self, page) -> str:
        selectors = (
            ".jobs-search__job-details--container .jobs-details-top-card",
            ".jobs-details-top-card",
            ".jobs-search__job-details--container",
            ".jobs-details",
        )
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() == 0:
                    continue
                if await locator.is_visible(timeout=1000):
                    return selector
            except Exception:
                continue
        return ""

    async def try_open_easy_apply_modal(self, page) -> bool:
        await self.dismiss_interfering_dialogs(page)
        root_selector = await self._job_detail_root_selector(page)
        if not root_selector:
            return False
        candidates = [
            page.locator(f'{root_selector} a[href*="/apply/"][href*="openSDUIApplyFlow=true"]').first,
            page.locator(f'{root_selector} [data-live-test-job-apply-button] button, {root_selector} button[data-live-test-job-apply-button]').first,
            page.locator(f'{root_selector} [data-control-name="jobdetails_topcard_inapply"]').first,
            page.locator(f'{root_selector} [data-control-name="topcard_inapply"]').first,
            page.locator(f'{root_selector} [data-control-name="jobs-details-top-card-apply-button"]').first,
            page.locator(f'{root_selector} .jobs-apply-button--top-card button').first,
            page.locator(f'{root_selector} .jobs-s-apply button').first,
            page.locator(f'{root_selector} button.jobs-apply-button').first,
            page.locator(f'{root_selector} button[aria-label*="Easy Apply" i]').first,
            page.locator(f'{root_selector} button[aria-label*="Candidatura simplificada" i]').first,
            page.locator(f"{root_selector}").get_by_role(
                "button",
                name=re.compile(r"(easy apply|candidatura simplificada)", re.IGNORECASE),
            ).first,
            page.locator(f"{root_selector} button").filter(
                has_text=re.compile(r"(easy apply|candidatura simplificada)", re.IGNORECASE)
            ).first,
        ]
        for candidate in candidates:
            try:
                if await candidate.count() == 0:
                    continue
                try:
                    if not await candidate.is_visible(timeout=1000):
                        continue
                except Exception:
                    continue
                await candidate.scroll_into_view_if_needed()
                await page.wait_for_timeout(400)
                try:
                    await candidate.hover(timeout=1500)
                except Exception:
                    pass
                await candidate.click(timeout=3500)
                if await self.wait_for_apply_flow(page):
                    return True
                if await self.handle_save_application_dialog(page):
                    await page.wait_for_timeout(800)
                    continue
                await candidate.click(timeout=3500, force=True)
                if await self.wait_for_apply_flow(page):
                    return True
                if await self.handle_save_application_dialog(page):
                    await page.wait_for_timeout(800)
                    continue
                handle = await candidate.element_handle()
                if handle is not None:
                    await page.evaluate("(element) => element.click()", handle)
                    if await self.wait_for_apply_flow(page):
                        return True
                    if await self.handle_save_application_dialog(page):
                        await page.wait_for_timeout(800)
                        continue
            except Exception:
                continue
        direct_apply_url = await self.extract_easy_apply_href(page)
        if direct_apply_url:
            try:
                await page.goto(direct_apply_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(1400)
                if await self.wait_for_apply_flow(page):
                    return True
            except Exception:
                if is_page_closed(page):
                    return False
        fallback_opened = await page.evaluate(
            """
            (rootSelector) => {{
              const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
              const isExcludedNode = (node) => !!node?.closest(
                '[componentkey^="JobDetailsSimilarJobsSlot_"], [data-sdui-component*="similarJobs"]'
              );
              const root = document.querySelector(rootSelector);
              if (!root) return false;
              const seen = new Set();
              const candidates = [];
              for (const element of Array.from(root.querySelectorAll('button, a'))) {{
                if (isExcludedNode(element)) continue;
                if (seen.has(element)) continue;
                seen.add(element);
                candidates.push(element);
              }
              for (const element of candidates) {{
                const href = (element.getAttribute('href') || '').toLowerCase();
                const text = normalize(element.textContent);
                const aria = normalize(element.getAttribute('aria-label') || '');
                const control = normalize(element.getAttribute('data-control-name') || '');
                const matchesText = text.includes('easy apply') || text.includes('candidatura simplificada');
                const matchesAria = aria.includes('easy apply') || aria.includes('candidatura simplificada');
                const matchesControl = control.includes('inapply') || control.includes('apply-button');
                if (href.includes('/jobs/collections/similar-jobs/')) continue;
                if (element.tagName === 'A' && !href.includes('/apply/')) continue;
                if (!(matchesText || matchesAria || matchesControl)) continue;
                element.click();
                return true;
              }
              return false;
            }}
            """,
            root_selector,
        )
        if fallback_opened and await self.wait_for_apply_flow(page):
            return True
        await self.handle_save_application_dialog(page)
        await self.dismiss_interfering_dialogs(page)
        return False

    async def extract_easy_apply_href(self, page) -> str:
        root_selector = await self._job_detail_root_selector(page)
        if not root_selector:
            return ""
        try:
            href = await page.evaluate(
                """
                (rootSelector) => {
                  const isExcludedNode = (node) => !!node?.closest(
                    '[componentkey^="JobDetailsSimilarJobsSlot_"], [data-sdui-component*="similarJobs"]'
                  );
                  const root = document.querySelector(rootSelector);
                  if (!root) return '';
                  for (const element of Array.from(root.querySelectorAll('a[href*="/apply/"]'))) {
                    if (isExcludedNode(element)) continue;
                    const href = element.href || '';
                    if (!href.includes('/apply/')) continue;
                    const aria = (element.getAttribute('aria-label') || '').toLowerCase();
                    const text = (element.textContent || '').toLowerCase();
                    if (
                      href.includes('openSDUIApplyFlow=true') ||
                      aria.includes('easy apply') ||
                      aria.includes('candidatura simplificada') ||
                      text.includes('easy apply') ||
                      text.includes('candidatura simplificada')
                    ) {
                      return href;
                    }
                  }
                  return '';
                }
                """,
                root_selector,
            )
        except Exception:
            return ""
        return href if isinstance(href, str) else ""

    async def wait_for_apply_flow(self, page) -> bool:
        if await self.wait_for_modal(page):
            return True
        try:
            await page.wait_for_url(re.compile(r"/apply/|openSDUIApplyFlow=true", re.IGNORECASE), timeout=4500)
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1400)
            return True
        except Exception:
            return False

    async def wait_for_modal(self, page) -> bool:
        try:
            await page.locator('[role="dialog"], .jobs-easy-apply-modal, .artdeco-modal').first.wait_for(state="visible", timeout=4500)
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1400)
            return True
        except Exception:
            if is_page_closed(page):
                return False
            await self.handle_save_application_dialog(page)
            return False

    async def prepare_job_page_for_apply(self, page) -> None:
        try:
            await page.locator("main").first.wait_for(state="visible", timeout=5000)
        except Exception:
            return
        await page.wait_for_timeout(1200)
        await self.dismiss_interfering_dialogs(page)
        await page.evaluate(
            """
            () => {
              const target =
                document.querySelector('.jobs-details-top-card') ||
                document.querySelector('.jobs-search__job-details--container [data-live-test-job-apply-button]') ||
                document.querySelector('[data-live-test-job-apply-button]') ||
                document.querySelector('.jobs-search__job-details--container') ||
                document.querySelector('main');
              if (target) {
                target.scrollIntoView({ behavior: 'instant', block: 'center' });
              }
            }
            """
        )
        await page.wait_for_timeout(600)

    async def dismiss_interfering_dialogs(self, page) -> None:
        if await self.handle_save_application_dialog(page):
            return
        candidates = [
            page.get_by_role("button", name=re.compile(r"(dismiss|close|fechar|cancel|cancelar|not now|agora nao|agora nÃ£o|skip)", re.IGNORECASE)).first,
            page.locator('[role="dialog"] button[aria-label*="Dismiss"], [role="dialog"] button[aria-label*="Close"], [role="dialog"] button[aria-label*="Fechar"]').first,
            page.locator('button[aria-label*="Dismiss"], button[aria-label*="Close"], button[aria-label*="Fechar"]').first,
        ]
        for candidate in candidates:
            try:
                if await candidate.count() == 0:
                    continue
                await candidate.click(timeout=1500)
                await page.wait_for_timeout(500)
            except Exception:
                continue

    async def handle_save_application_dialog(self, page) -> bool:
        if is_page_closed(page):
            return False
        candidates = [
            page.locator('[role="alertdialog"] [data-control-name="discard_application_confirm_btn"]').first,
            page.locator('[role="alertdialog"] button').filter(has_text=re.compile(r"(discard|descartar)", re.IGNORECASE)).first,
            page.get_by_role("button", name=re.compile(r"^(discard|descartar)$", re.IGNORECASE)).first,
        ]
        for candidate in candidates:
            try:
                if await candidate.count() == 0:
                    continue
                await candidate.click(timeout=2000, force=True)
                await page.wait_for_timeout(900)
                return True
            except Exception:
                continue
        return False
