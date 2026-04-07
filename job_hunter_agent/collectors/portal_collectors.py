from __future__ import annotations

import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from job_hunter_agent.core.browser_support import (
    automation_result_to_text,
    build_available_file_paths,
    extract_json_object,
    resolve_local_chromium,
)
from job_hunter_agent.core.domain import RawJob, SiteConfig
from job_hunter_agent.collectors.linkedin import LinkedInDeterministicCollector
from job_hunter_agent.llm.scoring import standardize_error_message


logger = logging.getLogger(__name__)


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
        available_file_paths = build_available_file_paths(self.config_dir)
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
        return resolve_local_chromium()


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
        known_job_url_exists: Callable[[str], bool] | None = None,
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
        self.linkedin_collector = linkedin_collector or LinkedInDeterministicCollector(
            storage_state_path=resolved_storage_state,
            headless=headless,
            known_job_url_exists=known_job_url_exists,
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
        result_text = automation_result_to_text(result)
        payload = extract_json_object(result_text)
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
