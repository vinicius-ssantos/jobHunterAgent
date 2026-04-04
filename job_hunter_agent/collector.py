from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from job_hunter_agent.browser_support import (
    automation_result_to_text as browser_automation_result_to_text,
    build_available_file_paths as browser_build_available_file_paths,
    extract_json_object as browser_extract_json_object,
    resolve_local_chromium as browser_resolve_local_chromium,
)
from job_hunter_agent.domain import CollectionReport, JobPosting, RawJob, ScoredJob, SiteConfig
from job_hunter_agent.linkedin import (
    LinkedInDeterministicCollector as ModularLinkedInDeterministicCollector,
    OllamaLinkedInFieldRepairer as ModularOllamaLinkedInFieldRepairer,
)
from job_hunter_agent.repository import JobRepository
from job_hunter_agent.settings import Settings


logger = logging.getLogger(__name__)


class SiteCollector(Protocol):
    async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
        raise NotImplementedError


class JobScorer(Protocol):
    def score(self, raw_job: RawJob, settings: Settings) -> ScoredJob:
        raise NotImplementedError


class BrowserAutomationAdapter(Protocol):
    async def run(self, task: str, site: SiteConfig | None = None) -> object:
        raise NotImplementedError


class PortalCollectorAdapter(Protocol):
    def supports(self, site: SiteConfig) -> bool:
        raise NotImplementedError

    def build_task(self, site: SiteConfig, max_jobs: int) -> str:
        raise NotImplementedError

    def normalize(self, site: SiteConfig, payload: dict) -> list[RawJob]:
        raise NotImplementedError


class DeterministicPortalCollector(Protocol):
    async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
        raise NotImplementedError


class BrowserUseAutomationAdapter:
    def __init__(
        self,
        model_name: str,
        base_url: str,
        config_dir: str | Path | None = None,
        persistent_profile_dir: str | Path | None = None,
        linkedin_storage_state_path: str | Path | None = None,
        *,
        headless: bool = True,
    ) -> None:
        resolved_config_dir = Path(config_dir or "./.browseruse").resolve()
        resolved_config_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("BROWSER_USE_CONFIG_DIR", str(resolved_config_dir))

        try:
            from browser_use import Agent, BrowserProfile, BrowserSession, ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de coleta nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc

        self._agent_cls = Agent
        self._browser_profile_cls = BrowserProfile
        self._browser_session_cls = BrowserSession
        self._llm_cls = ChatOllama
        self.model_name = model_name
        self.base_url = base_url
        self.config_dir = resolved_config_dir
        self.persistent_profile_dir = Path(
            persistent_profile_dir or resolved_config_dir / "profiles" / "linkedin-persistent"
        ).resolve()
        self.persistent_profile_dir.mkdir(parents=True, exist_ok=True)
        self.linkedin_storage_state_path = Path(
            linkedin_storage_state_path or resolved_config_dir / "linkedin-storage-state.json"
        ).resolve()
        self.headless = headless

    async def run(self, task: str, site: SiteConfig | None = None) -> object:
        executable_path = self._resolve_local_chromium()
        available_file_paths = browser_build_available_file_paths(self.config_dir)
        browser_profile = self._build_browser_profile(site, executable_path)
        browser = self._browser_session_cls(browser_profile=browser_profile)
        llm = self._llm_cls(model=self.model_name, host=self.base_url)
        agent = self._agent_cls(
            task=task,
            llm=llm,
            browser=browser,
            available_file_paths=available_file_paths,
        )
        try:
            result = await agent.run()
        finally:
            await browser.stop()
        return result

    def _build_browser_profile(self, site: SiteConfig | None, executable_path: Path) -> object:
        profile_kwargs = {
            "headless": self.headless,
            "executable_path": executable_path,
            "chromium_sandbox": False,
            "enable_default_extensions": False,
            "downloads_path": self.config_dir / "downloads",
        }
        if site and site.name.lower() == "linkedin" and self.linkedin_storage_state_path.exists():
            profile_kwargs["storage_state"] = self.linkedin_storage_state_path
        else:
            profile_kwargs["user_data_dir"] = self._resolve_user_data_dir(site)
        return self._browser_profile_cls(**profile_kwargs)

    def _resolve_user_data_dir(self, site: SiteConfig | None) -> Path:
        if site and site.name.lower() == "linkedin" and not self.linkedin_storage_state_path.exists():
            return self.persistent_profile_dir
        return Path(tempfile.mkdtemp(prefix="job-hunter-browser-", dir=self.config_dir))

    def _resolve_local_chromium(self) -> Path:
        return browser_resolve_local_chromium()


@dataclass(frozen=True)
class BasePortalCollectorAdapter:
    portal_name: str
    portal_hint: str

    def supports(self, site: SiteConfig) -> bool:
        return site.name.lower() == self.portal_name.lower()

    def build_task(self, site: SiteConfig, max_jobs: int) -> str:
        return f"""
        Abra a busca de vagas em {site.search_url}.
        Voce esta operando no portal {site.name}.
        {self.portal_hint}

        Colete no maximo {max_jobs} vagas de tecnologia da lista inicial.
        Abra detalhes apenas quando necessario para enriquecer os campos.

        Para cada vaga, retorne:
        - title
        - company
        - location
        - work_mode
        - salary_text
        - url
        - summary
        - description

        Regras:
        - priorize links diretos da vaga
        - se um campo nao estiver disponivel, use texto curto como fallback
        - nao retorne texto fora do JSON

        Responda apenas JSON no formato:
        {{
          "jobs": [
            {{
              "title": "...",
              "company": "...",
              "location": "...",
              "work_mode": "...",
              "salary_text": "...",
              "url": "...",
              "summary": "...",
              "description": "..."
            }}
          ]
        }}
        """

    def normalize(self, site: SiteConfig, payload: dict) -> list[RawJob]:
        jobs: list[RawJob] = []
        for item in payload.get("jobs", []):
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            if not title or not url:
                continue
            jobs.append(
                RawJob(
                    title=title,
                    company=str(item.get("company", "")).strip() or "Empresa nao informada",
                    location=str(item.get("location", "")).strip() or "Local nao informado",
                    work_mode=str(item.get("work_mode", "")).strip() or "Nao informado",
                    salary_text=str(item.get("salary_text", "")).strip() or "Nao informado",
                    url=url,
                    source_site=site.name,
                    summary=str(item.get("summary", "")).strip(),
                    description=str(item.get("description", "")).strip(),
                )
            )
        return jobs


class LinkedInCollectorAdapter(BasePortalCollectorAdapter):
    def __init__(self) -> None:
        super().__init__(
            portal_name="LinkedIn",
            portal_hint=(
                "Priorize vagas com contexto de LinkedIn Jobs. "
                "Tente capturar localidade, modalidade de trabalho e sinais de senioridade. "
                "Quando houver pagina de detalhes, resuma a stack pedida em summary. "
                "Se aparecer modal ou pop-up pedindo login, tente fecha-lo antes de continuar. "
                "Se o portal bloquear a listagem sem login, retorne {'jobs': []} sem inventar dados."
            ),
        )

    def build_task(self, site: SiteConfig, max_jobs: int) -> str:
        base_task = super().build_task(site, max_jobs)
        return (
            f"{base_task}\n\n"
            "Tratamento especifico para o LinkedIn:\n"
            "- Este fluxo e exclusivamente sobre vagas. Nunca trate a pagina como e-commerce, catalogo, produto, loja ou checkout.\n"
            "- Nunca procure, extraia ou role ate textos como 'Product Name', 'Price', 'Add to cart', 'Buy now', 'SKU', 'Checkout' ou equivalentes.\n"
            "- Nunca use queries, XPath, seletores ou labels relacionados a produto, preco, carrinho, catalogo ou ficha tecnica.\n"
            "- Extraia apenas sinais de vaga: titulo, empresa, localidade, modalidade, senioridade, faixa salarial quando houver, link absoluto da vaga e resumo/descricao.\n"
            "- Se aparecer um modal com textos como 'Entre para ver mais vagas', "
            "'Entrar com e-mail' ou 'Nunca usou o LinkedIn? Cadastre-se agora', trate isso como bloqueio de login.\n"
            "- O modal pode usar classes contendo 'contextual-sign-in-modal'.\n"
            "- Nunca clique em botoes de login, cadastro, Google sign-in, 'Entrar com e-mail' ou campos de credenciais.\n"
            "- Antes de desistir, tente fechar o modal com o botao de fechar visivel. "
            "Priorize botoes com aria-label='Fechar' ou classes como "
            "'modal__dismiss contextual-sign-in-modal__modal-dismiss'.\n"
            "- Se o botao de fechar nao funcionar, tente Escape e depois clique fora do modal.\n"
            "- Nao preencha credenciais e nao tente autenticar.\n"
            "- Se o modal continuar bloqueando a lista de vagas, retorne exatamente {'jobs': []}.\n"
            "- So colete vagas realmente visiveis na pagina apos remover ou contornar o modal.\n"
            "- Nunca navegue para textos, labels, placeholders, JSONPath ou expressoes como "
            "'$.results[0][...]', '@aria-label', 'aria-label' ou conteudo que nao seja URL real.\n"
            "- Nunca navegue para '#', 'javascript:', links vazios, ancora local ou qualquer valor que nao seja URL absoluta valida.\n"
            "- So use navigate se a string comecar com 'https://'. Caso contrario, nao navegue.\n"
            "- Se precisar abrir a vaga, prefira clicar no card visivel da vaga na lista em vez de construir uma URL manualmente.\n"
            "- Ao preencher o campo 'url' no JSON, use apenas links absolutos validos iniciando com 'https://'.\n"
            "- Se nao houver href absoluto confiavel para a vaga, mantenha a coleta na lista e extraia apenas o que estiver visivel.\n"
        )


class GupyCollectorAdapter(BasePortalCollectorAdapter):
    def __init__(self) -> None:
        super().__init__(
            portal_name="Gupy",
            portal_hint=(
                "Priorize o titulo da vaga, empresa, local e descricao curta do fluxo da Gupy. "
                "Se o link direto da vaga estiver disponivel, use-o."
            ),
        )


class IndeedCollectorAdapter(BasePortalCollectorAdapter):
    def __init__(self) -> None:
        super().__init__(
            portal_name="Indeed",
            portal_hint=(
                "Priorize o titulo da vaga, empresa, local, faixa salarial quando houver "
                "e um resumo enxuto da oportunidade."
            ),
        )


class DefaultPortalCollectorAdapter(BasePortalCollectorAdapter):
    def __init__(self) -> None:
        super().__init__(
            portal_name="__default__",
            portal_hint="Colete vagas genericas de tecnologia com estrutura consistente.",
        )

    def supports(self, site: SiteConfig) -> bool:
        return True


class LinkedInDeterministicCollector:
    def __init__(
        self,
        *,
        storage_state_path: str | Path,
        headless: bool,
        field_repairer: LinkedInFieldRepairer | None = None,
    ) -> None:
        self.storage_state_path = Path(storage_state_path).resolve()
        self.headless = headless
        self.field_repairer = field_repairer

    async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
        if not self.storage_state_path.exists():
            raise RuntimeError(
                "Sessao autenticada do LinkedIn nao encontrada. Rode --bootstrap-linkedin-session."
            )

        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de coleta nao estao instaladas. Rode pip install -r requirements.txt."
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
                await page.goto(site.search_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                await self._dismiss_sign_in_modal(page)
                try:
                    await page.wait_for_selector("a[href*='/jobs/view/']", timeout=10000)
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError(
                        "nenhum card de vaga do LinkedIn ficou visivel apos carregar a busca"
                    ) from exc
                raw_cards = await self._extract_visible_cards(page, max_jobs)
                enriched_cards = await self._enrich_residual_cards(context, raw_cards)
            finally:
                await context.close()
                await browser.close()

        jobs: list[RawJob] = []
        seen_urls: set[str] = set()
        for card in enriched_cards:
            normalized_card = normalize_linkedin_card(card)
            if self.field_repairer and should_repair_linkedin_fields(normalized_card):
                repaired_fields = self.field_repairer.repair(card, normalized_card)
                repaired_card = apply_linkedin_field_repair(normalized_card, repaired_fields)
                if repaired_card != normalized_card:
                    logger.info(
                        "LinkedIn card reparado por LLM local | title=%r company=%r location=%r",
                        repaired_card["title"].strip(),
                        repaired_card["company"].strip() or "Empresa nao informada",
                        repaired_card["location"].strip() or "Local nao informado",
                    )
                normalized_card = repaired_card
            url = normalized_card["url"].strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            company = normalized_card["company"].strip() or "Empresa nao informada"
            location = normalized_card["location"].strip() or "Local nao informado"
            if company == "Empresa nao informada" or location == "Local nao informado":
                logger.warning(
                    "LinkedIn card residual sem company/location | title=%r company=%r location=%r raw=%s",
                    normalized_card["title"].strip(),
                    company,
                    location,
                    summarize_linkedin_raw_card(card),
                )
            jobs.append(
                RawJob(
                    title=normalized_card["title"].strip(),
                    company=company,
                    location=location,
                    work_mode=normalized_card["work_mode"].strip() or "Nao informado",
                    salary_text=normalized_card["salary_text"].strip() or "Nao informado",
                    url=url,
                    source_site=site.name,
                    summary=normalized_card["summary"].strip(),
                    description=normalized_card["description"].strip(),
                )
            )
        return jobs

    async def _enrich_residual_cards(self, context: object, cards: list[dict[str, str]]) -> list[dict[str, str]]:
        enriched_cards: list[dict[str, str]] = []
        for card in cards:
            normalized_card = normalize_linkedin_card(card)
            if not should_enrich_linkedin_card(normalized_card):
                enriched_cards.append(card)
                continue
            detail = await self._extract_job_detail_snapshot(context, normalized_card["url"].strip())
            if not detail:
                enriched_cards.append(card)
                continue
            merged_card = merge_linkedin_card_with_detail(card, detail)
            merged_normalized = normalize_linkedin_card(merged_card)
            logger.info(
                "LinkedIn card enriquecido pelo detalhe | title=%r company=%r location=%r",
                merged_normalized["title"].strip(),
                merged_normalized["company"].strip() or "Empresa nao informada",
                merged_normalized["location"].strip() or "Local nao informado",
            )
            enriched_cards.append(merged_card)
        return enriched_cards

    async def _extract_job_detail_snapshot(self, context: object, url: str) -> dict[str, str]:
        if not url.startswith("https://"):
            return {}
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            return await page.evaluate(
                """
                () => {
                  const normalizeText = (value) => (value || "").replace(/\\s+/g, " ").trim();
                  const textsForSelectors = (selectors) => {
                    const values = [];
                    for (const selector of selectors) {
                      for (const node of Array.from(document.querySelectorAll(selector))) {
                        const text = normalizeText(node.textContent || "");
                        if (text && !values.includes(text)) {
                          values.push(text);
                        }
                      }
                    }
                    return values;
                  };
                  const companyCandidates = textsForSelectors([
                    ".job-details-jobs-unified-top-card__company-name a",
                    ".job-details-jobs-unified-top-card__company-name",
                    ".jobs-unified-top-card__company-name a",
                    ".jobs-unified-top-card__company-name",
                    ".job-details-jobs-unified-top-card__primary-description a",
                    ".job-details-jobs-unified-top-card__primary-description-container a",
                  ]);
                  const metadataCandidates = textsForSelectors([
                    ".job-details-jobs-unified-top-card__tertiary-description",
                    ".job-details-jobs-unified-top-card__tertiary-description-container",
                    ".job-details-jobs-unified-top-card__primary-description-container",
                    ".jobs-unified-top-card__subtitle-primary-grouping",
                    ".jobs-unified-top-card__bullet",
                  ]);
                  const title = normalizeText(
                    document.querySelector("h1")?.textContent ||
                    document.querySelector(".job-details-jobs-unified-top-card__job-title")?.textContent ||
                    ""
                  );
                  const summary = normalizeText(document.body?.innerText || "").slice(0, 400);
                  return {
                    title,
                    company: companyCandidates.join(" | "),
                    location: metadataCandidates.join(" | "),
                    summary,
                    raw_company_candidates: companyCandidates.join(" | "),
                    raw_metadata_candidates: metadataCandidates.join(" | "),
                  };
                }
                """
            )
        except Exception as exc:
            logger.warning("LinkedIn detail enrichment falhou | url=%r detalhe=%s", url, exc)
            return {}
        finally:
            await page.close()

    async def _dismiss_sign_in_modal(self, page: object) -> None:
        modal_button_selectors = (
            "button[aria-label='Fechar']",
            "button.contextual-sign-in-modal__modal-dismiss",
            "button.modal__dismiss",
        )
        for selector in modal_button_selectors:
            locator = page.locator(selector)
            if await locator.count():
                try:
                    await locator.first.click(timeout=1000)
                    await page.wait_for_timeout(500)
                    return
                except Exception:
                    continue

    async def _extract_visible_cards(self, page: object, max_jobs: int) -> list[dict[str, str]]:
        return await page.evaluate(
            """
            ({ maxJobs }) => {
              const anchors = Array.from(document.querySelectorAll("a[href*='/jobs/view/']"));
              const normalized = [];
              const seen = new Set();
              const normalizeHref = (href) => {
                if (!href) return "";
                try {
                  return new URL(href, window.location.origin).toString();
                } catch {
                  return "";
                }
              };
              for (const anchor of anchors) {
                const href = normalizeHref(anchor.getAttribute("href") || anchor.href || "");
                if (!href || !href.startsWith("https://") || seen.has(href)) {
                  continue;
                }
                const card = anchor.closest("li, .job-card-container, .jobs-search-results__list-item, .job-card-list");
                const rawText = (card?.innerText || anchor.innerText || "").trim();
                const cardText = rawText.replace(/\\s+/g, " ").trim();
                if (!cardText) {
                  continue;
                }
                const normalizeLine = (line) => (line || "").replace(/\\s+/g, " ").trim();
                const noiseMarkers = ["promovida", "candidatura simplificada", "avaliando candidaturas", "visualizado", "with verification"];
                const isNoiseLine = (line) => {
                  const lower = line.toLowerCase();
                  return noiseMarkers.some((marker) => lower.includes(marker)) || /\\b\\d+\\s+candidaturas\\b/i.test(lower);
                };
                const isLocationLine = (line) => {
                  const lower = line.toLowerCase();
                  return (
                    lower.includes("brasil") ||
                    lower.includes("são paulo") ||
                    lower.includes("sao paulo") ||
                    lower.includes("rio de janeiro") ||
                    lower.includes("(híbrido)") ||
                    lower.includes("(hibrido)") ||
                    lower.includes("(remoto)") ||
                    lower.includes("(presencial)") ||
                    lower.includes(" hybrid") ||
                    lower.includes(" remoto") ||
                    lower.includes(" presencial")
                  );
                };
                const lines = rawText
                  .split(/\\n+/)
                  .map((line) => normalizeLine(line))
                  .filter(Boolean);
                const selectorTexts = (selectors) => {
                  const values = [];
                  for (const selector of selectors) {
                    for (const node of Array.from(card?.querySelectorAll(selector) || [])) {
                      const text = normalizeLine(node.textContent || "");
                      if (text && !values.includes(text)) {
                        values.push(text);
                      }
                    }
                  }
                  return values;
                };
                const companyCandidates = selectorTexts([
                  ".job-card-container__primary-description",
                  ".artdeco-entity-lockup__subtitle",
                  ".artdeco-entity-lockup__subtitle span",
                ]);
                const metadataCandidates = selectorTexts([
                  ".job-card-container__metadata-item",
                  ".artdeco-entity-lockup__caption",
                  ".artdeco-entity-lockup__metadata",
                ]);
                const title = normalizeLine(lines[0] || anchor.textContent || "");
                if (!title) {
                  continue;
                }
                const filteredLines = lines.filter((line) => line !== title && !isNoiseLine(line));
                const company = (
                  companyCandidates.find((line) => line !== title && !isNoiseLine(line) && !isLocationLine(line)) ||
                  filteredLines.find((line) => line !== title && !isLocationLine(line)) ||
                  ""
                );
                const location = (
                  metadataCandidates.find((line) => isLocationLine(line)) ||
                  filteredLines.find((line) => isLocationLine(line)) ||
                  ""
                );
                const lowerText = cardText.toLowerCase();
                let workMode = "";
                if (lowerText.includes("remoto")) workMode = "remoto";
                else if (lowerText.includes("híbrido") || lowerText.includes("hibrido") || lowerText.includes("hybrid")) workMode = "hibrido";
                else if (lowerText.includes("presencial") || lowerText.includes("onsite")) workMode = "presencial";
                const salaryMatch = cardText.match(/R\\$\\s?[\\d\\.]+(?:\\s*[-a]\\s*R\\$?\\s?[\\d\\.]+)?/i);
                seen.add(href);
                normalized.push({
                  title,
                  company,
                  location,
                  work_mode: workMode,
                  salary_text: salaryMatch ? salaryMatch[0] : "",
                  url: href,
                  summary: cardText.slice(0, 240),
                  description: cardText.slice(0, 1000),
                  raw_lines: lines.join(" | "),
                  raw_company_candidates: companyCandidates.join(" | "),
                  raw_metadata_candidates: metadataCandidates.join(" | "),
                  anchor_text: normalizeLine(anchor.textContent || ""),
                });
                if (normalized.length >= maxJobs) {
                  break;
                }
              }
              return normalized;
            }
            """,
            {"maxJobs": max_jobs},
        )


class BrowserUseSiteCollector:
    def __init__(
        self,
        model_name: str,
        base_url: str,
        config_dir: str | Path | None = None,
        persistent_profile_dir: str | Path | None = None,
        linkedin_storage_state_path: str | Path | None = None,
        headless: bool = True,
        automation: BrowserAutomationAdapter | None = None,
        linkedin_collector: DeterministicPortalCollector | None = None,
        portal_adapters: tuple[PortalCollectorAdapter, ...] | None = None,
    ) -> None:
        resolved_storage_state = Path(
            linkedin_storage_state_path or Path(config_dir or "./.browseruse") / "linkedin-storage-state.json"
        ).resolve()
        self.automation = automation or BrowserUseAutomationAdapter(
            model_name=model_name,
            base_url=base_url,
            config_dir=config_dir,
            persistent_profile_dir=persistent_profile_dir,
            linkedin_storage_state_path=resolved_storage_state,
            headless=headless,
        )
        self.linkedin_collector = linkedin_collector or ModularLinkedInDeterministicCollector(
            storage_state_path=resolved_storage_state,
            headless=headless,
        )
        self.portal_adapters: tuple[PortalCollectorAdapter, ...] = portal_adapters or (
            LinkedInCollectorAdapter(),
            GupyCollectorAdapter(),
            IndeedCollectorAdapter(),
            DefaultPortalCollectorAdapter(),
        )

    async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
        if site.name.lower() == "linkedin":
            logger.info("Coletando vagas com estrategia deterministica site=%s", site.name)
            return await self.linkedin_collector.collect(site, max_jobs)
        adapter = self._adapter_for(site)
        logger.info("Coletando vagas com adapter=%s site=%s", adapter.__class__.__name__, site.name)
        task = adapter.build_task(site, max_jobs)
        logger.info(
            "Disparando automacao de coleta site=%s max_jobs=%s task_chars=%s",
            site.name,
            max_jobs,
            len(task),
        )
        started_at = time.monotonic()
        result = await self.automation.run(task, site)
        elapsed_seconds = time.monotonic() - started_at
        logger.info("Automacao concluida site=%s duracao=%.2fs", site.name, elapsed_seconds)
        result_text = browser_automation_result_to_text(result)
        payload = browser_extract_json_object(result_text)
        if result_text.strip() and not payload:
            logger.warning(
                standardize_error_message("erro de parsing", site.name, "resposta sem JSON valido"),
            )
            logger.info("Resposta bruta sem JSON valido site=%s trecho=%r", site.name, result_text[:240])
        jobs = adapter.normalize(site, payload)
        logger.info("Coleta concluida site=%s vagas=%s", site.name, len(jobs))
        return jobs

    def _adapter_for(self, site: SiteConfig) -> PortalCollectorAdapter:
        for adapter in self.portal_adapters:
            if adapter.supports(site):
                return adapter
        return DefaultPortalCollectorAdapter()


class HybridJobScorer:
    def __init__(self, model_name: str, base_url: str) -> None:
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de scoring nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc
        self._llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1)

    def score(self, raw_job: RawJob, settings: Settings) -> ScoredJob:
        combined_text = f"{raw_job.title} {raw_job.summary} {raw_job.description}".lower()
        if any(keyword in combined_text for keyword in settings.scoring_exclude_keywords):
            return ScoredJob(relevance=1, rationale="Contem termos excluidos do perfil.", accepted=False)

        prompt = f"""
        Avalie aderencia de uma vaga ao perfil profissional abaixo.

        Perfil:
        {settings.scoring_profile_text}

        Regras:
        - Nota de 1 a 10.
        - Considere palavras positivas: {", ".join(settings.include_keywords)}
        - Considere palavras negativas: {", ".join(settings.scoring_exclude_keywords)}
        - Modalidades aceitas: {", ".join(settings.accepted_work_modes) or "qualquer"}
        - Salario minimo em BRL: {settings.minimum_salary_brl}
        - Seja conservador. So aprove quando a vaga realmente fizer sentido.

        Vaga:
        titulo: {raw_job.title}
        empresa: {raw_job.company}
        local: {raw_job.location}
        modalidade: {raw_job.work_mode}
        salario: {raw_job.salary_text}
        resumo: {raw_job.summary}
        descricao: {raw_job.description}

        Retorne apenas JSON:
        {{
          "relevance": 7,
          "rationale": "motivo curto em portugues"
        }}
        """

        response = self._llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)
        return parse_scoring_response(response_text, settings.scoring_minimum_relevance)


class OllamaLinkedInFieldRepairer:
    def __init__(self, model_name: str, base_url: str) -> None:
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de repair do LinkedIn nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc
        self._llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.0)

    def repair(self, card: dict[str, str], normalized_card: dict[str, str]) -> dict[str, str]:
        prompt = f"""
        Corrija apenas campos de uma vaga do LinkedIn que parecem ausentes ou suspeitos.

        Regras:
        - Nunca invente dados que nao estejam no texto.
        - Se nao tiver confianca, retorne string vazia no campo.
        - Empresa deve ser o nome da empresa, nao cidade, nao texto de navegacao, nao titulo da vaga.
        - Local deve ser somente a localizacao da vaga.
        - Retorne apenas JSON.

        Campos atuais:
        title: {normalized_card.get("title", "")}
        company: {normalized_card.get("company", "")}
        location: {normalized_card.get("location", "")}
        work_mode: {normalized_card.get("work_mode", "")}
        summary: {normalized_card.get("summary", "")}

        Evidencias brutas:
        raw_company_candidates: {card.get("raw_company_candidates", "")}
        raw_metadata_candidates: {card.get("raw_metadata_candidates", "")}
        detail_company_candidates: {card.get("detail_company_candidates", "")}
        detail_metadata_candidates: {card.get("detail_metadata_candidates", "")}
        detail_summary: {card.get("detail_summary", "")}
        raw_lines: {card.get("raw_lines", "")}

        Retorne:
        {{
          "company": "nome ou vazio",
          "location": "local ou vazio",
          "confidence": 8,
          "rationale": "motivo curto"
        }}
        """
        response = self._llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)
        return parse_linkedin_field_repair_response(response_text)


class JobCollectionService:
    def __init__(
        self,
        settings: Settings,
        repository: JobRepository,
        site_collector: SiteCollector,
        scorer: JobScorer,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.site_collector = site_collector
        self.scorer = scorer

    async def collect_new_jobs(self) -> list[JobPosting]:
        return list((await self.collect_new_jobs_report()).jobs)

    async def collect_new_jobs_report(self) -> CollectionReport:
        saved_jobs: list[JobPosting] = []
        total_seen = 0
        total_errors = 0
        for site in [candidate for candidate in self.settings.sites if candidate.enabled]:
            try:
                logger.info(
                    "Iniciando coleta no portal site=%s timeout=%ss",
                    site.name,
                    self.settings.portal_collection_timeout_seconds,
                )
                started_at = time.monotonic()
                raw_jobs = await asyncio.wait_for(
                    self.site_collector.collect(site, self.settings.max_jobs_per_site),
                    timeout=self.settings.portal_collection_timeout_seconds,
                )
                elapsed_seconds = time.monotonic() - started_at
                logger.info("Portal concluido site=%s duracao=%.2fs", site.name, elapsed_seconds)
            except asyncio.TimeoutError:
                message = standardize_error_message(
                    "erro de coleta",
                    site.name,
                    f"timeout apos {self.settings.portal_collection_timeout_seconds}s",
                )
                logger.exception(message)
                self.repository.record_collection_log(site.name, "error", message)
                total_errors += 1
                continue
            except Exception as exc:
                message = standardize_error_message("erro de coleta", site.name, str(exc))
                logger.exception(message)
                self.repository.record_collection_log(site.name, "error", message)
                total_errors += 1
                continue

            total_seen += len(raw_jobs)
            scored_jobs = self._score_and_filter(raw_jobs)
            new_jobs = [job for job in scored_jobs if not self.repository.job_exists(job.url, job.external_key)]
            duplicate_jobs = len(scored_jobs) - len(new_jobs)
            saved_jobs.extend(self.repository.save_new_jobs(new_jobs))
            portal_summary = (
                f"resultado por portal site={site.name} "
                f"vistas={len(raw_jobs)} aprovadas={len(scored_jobs)} "
                f"persistidas={len(new_jobs)} duplicadas={duplicate_jobs}"
            )
            logger.info(portal_summary)
            self.repository.record_collection_log(
                site.name,
                "info",
                portal_summary,
            )

        saved_jobs.sort(key=lambda item: item.relevance, reverse=True)
        logger.info(
            "Ciclo de coleta finalizado: vistas=%s persistidas=%s erros=%s",
            total_seen,
            len(saved_jobs),
            total_errors,
        )
        return CollectionReport(
            jobs=tuple(saved_jobs),
            jobs_seen=total_seen,
            jobs_saved=len(saved_jobs),
            errors=total_errors,
        )

    def _score_and_filter(self, raw_jobs: list[RawJob]) -> list[JobPosting]:
        accepted_jobs: list[JobPosting] = []
        for raw_job in raw_jobs:
            if not self._is_minimally_valid(raw_job):
                logger.info("Vaga descartada por validade minima: %s", raw_job.title or "<sem titulo>")
                continue

            prefilter = self._apply_rule_filters(raw_job)
            if prefilter is not None:
                logger.info("Vaga descartada por regra: %s | motivo=%s", raw_job.title, prefilter)
                continue

            try:
                score = self.scorer.score(raw_job, self.settings)
            except Exception as exc:
                logger.exception(
                    standardize_error_message("erro de scoring", raw_job.source_site, str(exc)),
                )
                continue
            if not score.accepted:
                logger.info(
                    "Vaga descartada por score: %s | nota=%s | motivo=%s",
                    raw_job.title,
                    score.relevance,
                    score.rationale,
                )
                continue
            accepted_jobs.append(
                JobPosting(
                    title=raw_job.title,
                    company=raw_job.company,
                    location=raw_job.location,
                    work_mode=raw_job.work_mode,
                    salary_text=raw_job.salary_text,
                    url=raw_job.url,
                    source_site=raw_job.source_site,
                    summary=raw_job.summary or raw_job.description[:240],
                    relevance=score.relevance,
                    rationale=score.rationale,
                    external_key=build_external_key(raw_job),
                )
            )
        return accepted_jobs

    def _is_minimally_valid(self, raw_job: RawJob) -> bool:
        return bool(
            raw_job.title.strip()
            and raw_job.company.strip()
            and raw_job.url.strip()
            and raw_job.source_site.strip()
        )

    def _apply_rule_filters(self, raw_job: RawJob) -> str | None:
        combined_text = f"{raw_job.title} {raw_job.summary} {raw_job.description}".lower()
        if any(keyword in combined_text for keyword in self.settings.scoring_exclude_keywords):
            return "conta com termos excluidos"

        work_mode = raw_job.work_mode.strip().lower()
        if work_mode and work_mode not in {"nao informado", "não informado"}:
            if self.settings.accepted_work_modes and not any(mode in work_mode for mode in self.settings.accepted_work_modes):
                return "modalidade fora do perfil"

        salary_floor = parse_salary_floor(raw_job.salary_text)
        if salary_floor is not None and salary_floor < self.settings.minimum_salary_brl:
            return "salario abaixo do minimo"

        return None


def build_external_key(raw_job: RawJob) -> str:
    normalized = "|".join(
        [
            raw_job.title.strip().lower(),
            raw_job.company.strip().lower(),
            raw_job.location.strip().lower(),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def resolve_local_chromium() -> Path:
    browsers_root = Path(os.getenv("PLAYWRIGHT_BROWSERS_PATH", ".playwright-browsers")).resolve()
    candidates = sorted(browsers_root.rglob("chrome.exe"))
    if not candidates:
        raise RuntimeError(
            "Nenhum chrome.exe do Playwright foi encontrado. Configure PLAYWRIGHT_BROWSERS_PATH e rode playwright install chromium."
        )
    return candidates[0]


def load_playwright_storage_state(path: str | Path) -> dict:
    state = json.loads(Path(path).read_text(encoding="utf-8"))
    sanitized_cookies: list[dict] = []
    for cookie in state.get("cookies", []):
        sanitized = dict(cookie)
        partition_key = sanitized.get("partitionKey")
        if isinstance(partition_key, dict):
            top_level_site = partition_key.get("topLevelSite")
            if isinstance(top_level_site, str) and top_level_site.strip():
                sanitized["partitionKey"] = top_level_site
            else:
                sanitized.pop("partitionKey", None)
        elif partition_key is not None and not isinstance(partition_key, str):
            sanitized.pop("partitionKey", None)
        sanitized_cookies.append(sanitized)
    state["cookies"] = sanitized_cookies
    return state


def normalize_linkedin_card(card: dict[str, str]) -> dict[str, str]:
    title = clean_linkedin_title(card.get("title", ""))
    raw_company = str(card.get("company", ""))
    raw_location = str(card.get("location", ""))
    raw_summary = str(card.get("summary", ""))
    company = clean_linkedin_company(raw_company)
    location = clean_linkedin_location(raw_location)
    if not company:
        location_as_company = clean_linkedin_company(raw_location)
        if location_as_company and not looks_like_linkedin_location(location_as_company):
            company = location_as_company
    if not location:
        location = clean_linkedin_location(raw_summary)
    location = strip_title_prefix_from_location(location, title)
    inferred_company = infer_linkedin_company_from_summary(raw_summary, title, location)
    if inferred_company and is_suspicious_linkedin_company(company, location):
        company = inferred_company
    elif not company:
        company = inferred_company
    work_mode = normalize_linkedin_work_mode(card.get("work_mode", ""), location)
    salary_text = clean_linkedin_salary(card.get("salary_text", ""))
    summary = clean_linkedin_summary(card.get("summary", ""))
    description = clean_linkedin_description(card.get("description", ""))
    return {
        "title": title,
        "company": company,
        "location": location,
        "work_mode": work_mode,
        "salary_text": salary_text,
        "url": str(card.get("url", "")).strip(),
        "summary": summary,
        "description": description,
    }


def should_repair_linkedin_fields(card: dict[str, str]) -> bool:
    return is_suspicious_linkedin_company(card.get("company", ""), card.get("location", "")) or is_suspicious_linkedin_location(
        card.get("location", ""), card.get("title", "")
    )


def apply_linkedin_field_repair(card: dict[str, str], repaired_fields: dict[str, str]) -> dict[str, str]:
    merged = dict(card)
    repaired_company = clean_linkedin_company(repaired_fields.get("company", ""))
    repaired_location = strip_title_prefix_from_location(
        clean_linkedin_location(repaired_fields.get("location", "")) or repaired_fields.get("location", ""),
        card.get("title", ""),
    )
    if repaired_company and is_suspicious_linkedin_company(merged.get("company", ""), merged.get("location", "")):
        merged["company"] = repaired_company
    if repaired_location and is_suspicious_linkedin_location(merged.get("location", ""), merged.get("title", "")):
        merged["location"] = repaired_location
    return merged


def should_enrich_linkedin_card(card: dict[str, str]) -> bool:
    return not card.get("company", "").strip() or not card.get("location", "").strip()


def merge_linkedin_card_with_detail(card: dict[str, str], detail: dict[str, str]) -> dict[str, str]:
    merged = dict(card)
    title = detail.get("title", "").strip()
    company = detail.get("company", "").strip()
    location = detail.get("location", "").strip()
    summary = detail.get("summary", "").strip()
    if title and len(title) > len(str(merged.get("title", "")).strip()):
        merged["title"] = title
    if company:
        merged["company"] = company
    if location:
        merged["location"] = location
    existing_summary = str(merged.get("summary", "")).strip()
    if summary and len(summary) > len(existing_summary):
        merged["summary"] = summary
    if detail.get("raw_company_candidates"):
        merged["detail_company_candidates"] = detail["raw_company_candidates"]
    if detail.get("raw_metadata_candidates"):
        merged["detail_metadata_candidates"] = detail["raw_metadata_candidates"]
    if summary:
        merged["detail_summary"] = summary
    return merged


def strip_title_prefix_from_location(location: str, title: str) -> str:
    normalized_location = _normalize_whitespace(location)
    normalized_title = _normalize_whitespace(title)
    if not normalized_location or not normalized_title:
        return normalized_location
    lowered_location = normalized_location.lower()
    lowered_title = normalized_title.lower()
    if lowered_location.startswith(lowered_title + " "):
        normalized_location = _normalize_whitespace(normalized_location[len(normalized_title) :])
    return clean_linkedin_location(normalized_location) or normalized_location


def infer_linkedin_company_from_summary(summary: str, title: str, location: str) -> str:
    normalized_summary = strip_linkedin_chrome_prefix(_normalize_whitespace(summary))
    normalized_title = _normalize_whitespace(title)
    normalized_location = _normalize_whitespace(location)
    if not normalized_summary:
        return ""
    candidate = normalized_summary
    if normalized_title:
        candidate = re.sub(rf"^{re.escape(normalized_title)}\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(rf"\s*{re.escape(normalized_title)}$", "", candidate, flags=re.IGNORECASE)
    if normalized_location:
        candidate = re.sub(rf"\s*{re.escape(normalized_location)}.*$", "", candidate, flags=re.IGNORECASE)
    if normalized_title:
        candidate = re.sub(rf"\s*{re.escape(normalized_title)}$", "", candidate, flags=re.IGNORECASE)
    return clean_linkedin_company(candidate)


def is_suspicious_linkedin_company(company: str, location: str) -> bool:
    normalized_company = _normalize_whitespace(company)
    if not normalized_company:
        return True
    lower_company = normalized_company.lower()
    if normalized_company.endswith(",") and len(normalized_company.split()) <= 2:
        return True
    if lower_company in {
        "empresa nao informada",
        "local nao informado",
        "osasco",
        "osasco,",
        "são paulo",
        "sao paulo",
        "brasil",
    }:
        return True
    normalized_location = _normalize_whitespace(location)
    if normalized_location:
        first_segment = normalized_location.split(",", maxsplit=1)[0].strip().lower()
        if first_segment and lower_company == first_segment:
            return True
        if first_segment and lower_company == f"{first_segment},":
            return True
    return False


def is_suspicious_linkedin_location(location: str, title: str) -> bool:
    normalized_location = _normalize_whitespace(location)
    normalized_title = _normalize_whitespace(title)
    if not normalized_location:
        return True
    lower_location = normalized_location.lower()
    if lower_location in {"local nao informado", "não informado", "nao informado"}:
        return True
    if normalized_title and lower_location.startswith(normalized_title.lower() + " "):
        return True
    return not looks_like_linkedin_location(normalized_location)


def strip_linkedin_chrome_prefix(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    chrome_markers = (
        "Reative Premium:",
        "Para negócios",
        "Notificações",
        "Mensagens",
        "Minha rede",
        "Pular para conteúdo principal",
    )
    for marker in chrome_markers:
        marker_index = cleaned.lower().rfind(marker.lower())
        if marker_index != -1:
            cleaned = _normalize_whitespace(cleaned[marker_index + len(marker) :])
            break
    cleaned = re.sub(r"^\d+%\s+de\s+desconto\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def clean_linkedin_title(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    repeated_prefix = re.match(r"^(.{5,120}?)\s+\1$", cleaned, flags=re.IGNORECASE)
    if repeated_prefix:
        cleaned = repeated_prefix.group(1).strip()
    else:
        collapsed_repeat = _collapse_repeated_title(cleaned)
        if collapsed_repeat:
            cleaned = collapsed_repeat
    cleaned = re.sub(r"\s+with verification\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bwith verification\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bPromovida\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bCandidatura simplificada\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bAvaliando candidaturas\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bVisualizado\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = _normalize_whitespace(cleaned)
    if "\n" in value:
        first_line = _normalize_whitespace(value.splitlines()[0])
        if first_line:
            return clean_linkedin_title(first_line)
    parts = [part.strip() for part in cleaned.split("  ") if part.strip()]
    if parts:
        return parts[0]
    return cleaned


def clean_linkedin_company(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    repeated_prefix = re.match(r"^(.{10,80}?)\s+\1\s+(.+)$", cleaned, flags=re.IGNORECASE)
    if repeated_prefix:
        cleaned = repeated_prefix.group(2).strip()
    cleaned = re.sub(r"^with verification\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(Desenvolvedor|Engenheiro|Software Engineer|Backend|Fullstack)\b.*?\bwith verification\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+with verification\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(São Paulo|Sao Paulo|Rio de Janeiro).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    noise_phrases = (
        "Promovida",
        "Candidatura simplificada",
        "Avaliando candidaturas",
        "Visualizado",
        "1 conexão trabalha aqui",
        "há ",
    )
    segments = _split_linkedin_segments(cleaned)
    kept: list[str] = []
    for segment in segments:
        normalized_segment = _normalize_whitespace(segment)
        lower_segment = normalized_segment.lower()
        if any(phrase.lower() in segment.lower() for phrase in noise_phrases):
            continue
        if looks_like_linkedin_location(normalized_segment):
            continue
        if lower_segment in {"hibrido", "híbrido", "remoto", "presencial", "hybrid", "onsite"}:
            continue
        if normalized_segment.endswith(",") and len(normalized_segment.split()) <= 1:
            continue
        if lower_segment in {
            "osasco",
            "são paulo",
            "sao paulo",
            "rio de janeiro",
            "curitiba",
            "campinas",
            "porto alegre",
            "belo horizonte",
            "brasil",
            "brazil",
        }:
            continue
        if len(normalized_segment.split()) <= 1:
            continue
        kept.append(normalized_segment)
        break
    if kept:
        return kept[0]
    if (
        looks_like_linkedin_location(cleaned)
        or (cleaned.endswith(",") and len(cleaned.split()) <= 1)
        or cleaned.lower()
        in {
            "osasco",
            "osasco,",
            "são paulo",
            "sao paulo",
            "rio de janeiro",
            "curitiba",
            "campinas",
            "porto alegre",
            "belo horizonte",
            "brasil",
            "brazil",
        }
    ):
        return ""
    return cleaned


def clean_linkedin_location(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    snippet = _extract_linkedin_location_snippet(cleaned)
    if snippet:
        return snippet
    segments = _split_linkedin_segments(cleaned)
    for segment in segments:
        lower_segment = segment.lower()
        if len(segment) > 80:
            continue
        if any(
            marker in lower_segment
            for marker in (
                "with verification",
                "promovida",
                "candidatura simplificada",
                "avaliando candidaturas",
                "visualizado",
            )
        ):
            continue
        if looks_like_linkedin_location(segment):
            return segment
    return ""


def normalize_linkedin_work_mode(raw_work_mode: str, location: str) -> str:
    combined = f"{raw_work_mode} {location}".lower()
    if "remoto" in combined or "remote" in combined:
        return "remoto"
    if "híbrido" in combined or "hibrido" in combined or "hybrid" in combined:
        return "hibrido"
    if "presencial" in combined or "onsite" in combined:
        return "presencial"
    return _normalize_whitespace(raw_work_mode)


def clean_linkedin_salary(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    return cleaned if cleaned else "Nao informado"


def clean_linkedin_summary(value: str) -> str:
    return _clean_linkedin_text_block(value, limit=240)


def clean_linkedin_description(value: str) -> str:
    return _clean_linkedin_text_block(value, limit=1000)


def _clean_linkedin_text_block(value: str, *, limit: int) -> str:
    cleaned = _normalize_whitespace(value)
    noise_patterns = (
        r"\bPromovida\b",
        r"\bCandidatura simplificada\b",
        r"\bAvaliando candidaturas\b",
        r"\bVisualizado\b",
        r"\bwith verification\b",
        r"\b\d+\s+candidaturas\b",
        r"\bhá\s+\d+\s+\w+\b",
    )
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = _normalize_whitespace(cleaned)
    return cleaned[:limit]


def _split_linkedin_segments(value: str) -> list[str]:
    return [segment.strip() for segment in re.split(r"[·•|]", value) if segment.strip()]


def looks_like_linkedin_location(value: str) -> bool:
    normalized = _normalize_whitespace(value)
    if not normalized:
        return False

    lower = normalized.lower()
    if any(
        marker in lower
        for marker in (
            "(híbrido)",
            "(hibrido)",
            "(remoto)",
            "(presencial)",
            " hybrid",
            " remoto",
            " presencial",
        )
    ):
        return True

    if "," in normalized and "brasil" in lower:
        return True

    return lower in {"brasil", "brazil"}


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _extract_linkedin_location_snippet(value: str) -> str:
    lower_value = value.lower()
    brasil_index = lower_value.rfind("brasil")
    if brasil_index == -1:
        return ""
    window_start = max(0, brasil_index - 80)
    window_end = min(len(value), brasil_index + 40)
    tail = value[window_start:window_end]
    match = re.search(
        r"([A-Za-zÀ-ÿ]+(?: [A-Za-zÀ-ÿ]+){0,3},\s*"
        r"[A-Za-zÀ-ÿ]+(?: [A-Za-zÀ-ÿ]+){0,3},\s*"
        r"Brasil(?:\s+\((?:Híbrido|Hibrido|Remoto|Presencial)\))?)",
        tail,
        flags=re.IGNORECASE,
    )
    if match:
        candidate = _normalize_whitespace(match.group(1))
        first_segment = candidate.split(",", maxsplit=1)[0].lower()
        if "brasil" in first_segment or "verification" in first_segment:
            candidate = _normalize_whitespace(
                re.sub(r"^.*?\bbrasil\s+", "", candidate, count=1, flags=re.IGNORECASE)
            )
        return candidate
    return ""


def _collapse_repeated_title(value: str) -> str | None:
    cleaned = _normalize_whitespace(value)
    if not cleaned:
        return None
    length = len(cleaned)
    if length % 2 == 0:
        midpoint = length // 2
        left = cleaned[:midpoint].strip()
        right = cleaned[midpoint:].strip()
        if left and left == right:
            return left
    return None


def summarize_linkedin_raw_card(card: dict[str, str]) -> str:
    debug_fields = (
        "title",
        "company",
        "location",
        "work_mode",
        "raw_company_candidates",
        "raw_metadata_candidates",
        "detail_company_candidates",
        "detail_metadata_candidates",
        "detail_summary",
        "raw_lines",
        "anchor_text",
        "summary",
    )
    parts: list[str] = []
    for field in debug_fields:
        value = _normalize_whitespace(str(card.get(field, "")))
        if value:
            parts.append(f"{field}={value[:160]!r}")
    return " | ".join(parts)


def parse_linkedin_field_repair_response(response_text: str) -> dict[str, str]:
    payload = extract_json_object(response_text)
    if not payload:
        return {}
    company = _normalize_whitespace(str(payload.get("company", "")))
    location = _normalize_whitespace(str(payload.get("location", "")))
    confidence = payload.get("confidence")
    if isinstance(confidence, str) and confidence.isdigit():
        confidence = int(confidence)
    if not isinstance(confidence, int):
        confidence = 0
    if confidence < 7:
        return {}
    return {
        "company": company,
        "location": location,
        "rationale": _normalize_whitespace(str(payload.get("rationale", ""))),
    }


def build_available_file_paths(base_dir: Path, limit: int = 20) -> list[str]:
    paths: list[str] = []
    for index in range(1, limit + 1):
        relative = f"./screenshot{index}.png"
        absolute = (base_dir / f"screenshot{index}.png").resolve()
        paths.append(relative)
        paths.append(str(absolute))
    return paths


def automation_result_to_text(result: object) -> str:
    if isinstance(result, str):
        return result

    final_result = getattr(result, "final_result", None)
    if callable(final_result):
        extracted = final_result()
        if isinstance(extracted, str):
            return extracted

    return str(result)


def extract_json_object(result: object) -> dict:
    result_text = automation_result_to_text(result)
    start = result_text.find("{")
    end = result_text.rfind("}") + 1
    if start == -1 or end <= start:
        return {}
    try:
        return json.loads(result_text[start:end])
    except json.JSONDecodeError:
        return {}


def parse_scoring_response(response_text: str, minimum_relevance: int) -> ScoredJob:
    payload = extract_json_object(response_text)
    if not payload:
        return ScoredJob(
            relevance=1,
            rationale="Resposta do modelo sem JSON valido.",
            accepted=False,
        )

    try:
        relevance = int(payload.get("relevance", 0) or 0)
    except (TypeError, ValueError):
        relevance = 0

    relevance = max(1, min(relevance, 10))
    rationale = str(payload.get("rationale", "")).strip() or "Sem justificativa do modelo."
    accepted = relevance >= minimum_relevance
    return ScoredJob(relevance=relevance, rationale=rationale, accepted=accepted)


def parse_salary_floor(salary_text: str) -> int | None:
    normalized = salary_text.lower().replace(".", "").replace(",", ".")
    matches = re.findall(r"(\d{3,6}(?:\.\d{1,2})?)", normalized)
    if not matches:
        return None
    try:
        first_value = float(matches[0])
    except ValueError:
        return None
    return int(first_value)


def standardize_error_message(error_type: str, site_name: str, detail: str) -> str:
    return f"{error_type} | site={site_name} | detalhe={detail}"
