from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from job_hunter_agent.browser_support import (
    automation_result_to_text as browser_automation_result_to_text,
    build_available_file_paths as browser_build_available_file_paths,
    extract_json_object as browser_extract_json_object,
    load_playwright_storage_state as browser_load_playwright_storage_state,
    resolve_local_chromium as browser_resolve_local_chromium,
)
from job_hunter_agent.domain import CollectionReport, JobPosting, RawJob, ScoredJob, SiteConfig
from job_hunter_agent.linkedin import (
    LinkedInDeterministicCollector as ModularLinkedInDeterministicCollector,
    OllamaLinkedInFieldRepairer as ModularOllamaLinkedInFieldRepairer,
    apply_linkedin_field_repair as linkedin_apply_linkedin_field_repair,
    clean_linkedin_company as linkedin_clean_linkedin_company,
    clean_linkedin_description as linkedin_clean_linkedin_description,
    clean_linkedin_location as linkedin_clean_linkedin_location,
    clean_linkedin_salary as linkedin_clean_linkedin_salary,
    clean_linkedin_summary as linkedin_clean_linkedin_summary,
    clean_linkedin_title as linkedin_clean_linkedin_title,
    infer_linkedin_company_from_summary as linkedin_infer_linkedin_company_from_summary,
    is_suspicious_linkedin_company as linkedin_is_suspicious_linkedin_company,
    is_suspicious_linkedin_location as linkedin_is_suspicious_linkedin_location,
    merge_linkedin_card_with_detail as linkedin_merge_linkedin_card_with_detail,
    normalize_linkedin_card as linkedin_normalize_linkedin_card,
    normalize_linkedin_work_mode as linkedin_normalize_linkedin_work_mode,
    parse_linkedin_field_repair_response as linkedin_parse_linkedin_field_repair_response,
    should_enrich_linkedin_card as linkedin_should_enrich_linkedin_card,
    should_repair_linkedin_fields as linkedin_should_repair_linkedin_fields,
    strip_linkedin_chrome_prefix as linkedin_strip_linkedin_chrome_prefix,
    strip_title_prefix_from_location as linkedin_strip_title_prefix_from_location,
    summarize_linkedin_raw_card as linkedin_summarize_linkedin_raw_card,
)
from job_hunter_agent.repository import JobRepository
from job_hunter_agent.scoring import (
    HybridJobScorer as ModularHybridJobScorer,
    parse_salary_floor as scoring_parse_salary_floor,
    parse_scoring_response as scoring_parse_scoring_response,
    standardize_error_message as scoring_standardize_error_message,
)
from job_hunter_agent.settings import Settings


logger = logging.getLogger(__name__)


LinkedInDeterministicCollector = ModularLinkedInDeterministicCollector
OllamaLinkedInFieldRepairer = ModularOllamaLinkedInFieldRepairer
resolve_local_chromium = browser_resolve_local_chromium
load_playwright_storage_state = browser_load_playwright_storage_state
build_available_file_paths = browser_build_available_file_paths
automation_result_to_text = browser_automation_result_to_text
extract_json_object = browser_extract_json_object
normalize_linkedin_card = linkedin_normalize_linkedin_card
should_repair_linkedin_fields = linkedin_should_repair_linkedin_fields
apply_linkedin_field_repair = linkedin_apply_linkedin_field_repair
should_enrich_linkedin_card = linkedin_should_enrich_linkedin_card
merge_linkedin_card_with_detail = linkedin_merge_linkedin_card_with_detail
strip_title_prefix_from_location = linkedin_strip_title_prefix_from_location
infer_linkedin_company_from_summary = linkedin_infer_linkedin_company_from_summary
is_suspicious_linkedin_company = linkedin_is_suspicious_linkedin_company
is_suspicious_linkedin_location = linkedin_is_suspicious_linkedin_location
strip_linkedin_chrome_prefix = linkedin_strip_linkedin_chrome_prefix
clean_linkedin_title = linkedin_clean_linkedin_title
clean_linkedin_company = linkedin_clean_linkedin_company
clean_linkedin_location = linkedin_clean_linkedin_location
normalize_linkedin_work_mode = linkedin_normalize_linkedin_work_mode
clean_linkedin_salary = linkedin_clean_linkedin_salary
clean_linkedin_summary = linkedin_clean_linkedin_summary
clean_linkedin_description = linkedin_clean_linkedin_description
summarize_linkedin_raw_card = linkedin_summarize_linkedin_raw_card
parse_linkedin_field_repair_response = linkedin_parse_linkedin_field_repair_response
HybridJobScorer = ModularHybridJobScorer
parse_scoring_response = scoring_parse_scoring_response
parse_salary_floor = scoring_parse_salary_floor
standardize_error_message = scoring_standardize_error_message


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
        if work_mode and work_mode not in {"nao informado", "nÃ£o informado"}:
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


