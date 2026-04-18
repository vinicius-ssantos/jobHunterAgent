from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Protocol

from job_hunter_agent.core.browser_support import (
    automation_result_to_text,
    build_available_file_paths,
    extract_json_object,
    load_playwright_storage_state,
    resolve_local_chromium,
)
from job_hunter_agent.core.domain import CollectionReport, JobPosting, RawJob, ScoredJob, SiteConfig
from job_hunter_agent.core.runtime_matching import RuntimeMatchingPolicy, RuntimeMatchingProfile
from job_hunter_agent.collectors.linkedin import (
    LinkedInDeterministicCollector,
    OllamaLinkedInFieldRepairer,
    apply_linkedin_field_repair,
    clean_linkedin_company,
    clean_linkedin_description,
    clean_linkedin_location,
    clean_linkedin_salary,
    clean_linkedin_summary,
    clean_linkedin_title,
    infer_linkedin_company_from_summary,
    is_suspicious_linkedin_company,
    is_suspicious_linkedin_location,
    merge_linkedin_card_with_detail,
    normalize_linkedin_card,
    normalize_linkedin_work_mode,
    parse_linkedin_field_repair_response,
    should_enrich_linkedin_card,
    should_repair_linkedin_fields,
    strip_linkedin_chrome_prefix,
    strip_title_prefix_from_location,
    summarize_linkedin_raw_card,
)
from job_hunter_agent.core.settings import Settings
from job_hunter_agent.infrastructure.repository import JobRepository
from job_hunter_agent.llm.scoring import HybridJobScorer, parse_salary_floor, parse_scoring_response, standardize_error_message

logger = logging.getLogger(__name__)


class SiteCollector(Protocol):
    async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
        raise NotImplementedError


class JobScorer(Protocol):
    def score(self, raw_job: RawJob, runtime_matching_profile: RuntimeMatchingProfile) -> ScoredJob:
        raise NotImplementedError


class JobCollectionService:
    def __init__(
        self,
        settings: Settings,
        runtime_matching_profile: RuntimeMatchingProfile,
        repository: JobRepository,
        site_collector: SiteCollector,
        scorer: JobScorer,
    ) -> None:
        self.settings = settings
        self.runtime_matching_profile = runtime_matching_profile
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
                raw_jobs = await asyncio.wait_for(
                    self.site_collector.collect(site, self.settings.max_jobs_per_site),
                    timeout=self.settings.portal_collection_timeout_seconds,
                )
                logger.info("Portal concluido site=%s", site.name)
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
            new_raw_jobs = self._filter_known_raw_jobs(raw_jobs)
            duplicate_jobs = len(raw_jobs) - len(new_raw_jobs)
            scored_jobs = self._score_and_filter(new_raw_jobs)
            new_jobs = [job for job in scored_jobs if not self.repository.job_exists(job.url, job.external_key)]
            duplicate_jobs += len(scored_jobs) - len(new_jobs)
            saved_jobs.extend(self.repository.save_new_jobs(new_jobs))
            portal_summary = (
                f"resultado por portal site={site.name} "
                f"vistas={len(raw_jobs)} aprovadas={len(scored_jobs)} "
                f"persistidas={len(new_jobs)} duplicadas={duplicate_jobs}"
            )
            logger.info(portal_summary)
            self.repository.record_collection_log(site.name, "info", portal_summary)

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

    def _filter_known_raw_jobs(self, raw_jobs: list[RawJob]) -> list[RawJob]:
        filtered: list[RawJob] = []
        skipped = 0
        for raw_job in raw_jobs:
            external_key = build_external_key(raw_job)
            if self.repository.job_exists(raw_job.url, external_key) or self.repository.seen_job_exists(
                raw_job.url,
                external_key,
            ):
                skipped += 1
                continue
            filtered.append(raw_job)
        if skipped:
            logger.info("Pipeline pulou %s vaga(s) ja conhecidas antes do scoring.", skipped)
        return filtered

    def _score_and_filter(self, raw_jobs: list[RawJob]) -> list[JobPosting]:
        accepted_jobs: list[JobPosting] = []
        for raw_job in raw_jobs:
            if not self._is_minimally_valid(raw_job):
                logger.info("Vaga descartada por validade minima: %s", raw_job.title or "<sem titulo>")
                continue

            prefilter = self._apply_rule_filters(raw_job)
            if prefilter is not None:
                self.repository.remember_seen_job(
                    raw_job.url,
                    build_external_key(raw_job),
                    raw_job.source_site,
                    f"discarded_rule:{prefilter}",
                )
                logger.info("Vaga descartada por regra: %s | motivo=%s", raw_job.title, prefilter)
                continue

            try:
                score = self.scorer.score(raw_job, self.runtime_matching_profile)
            except Exception as exc:
                logger.exception(standardize_error_message("erro de scoring", raw_job.source_site, str(exc)))
                continue
            if not score.accepted:
                self.repository.remember_seen_job(
                    raw_job.url,
                    build_external_key(raw_job),
                    raw_job.source_site,
                    f"discarded_score:{score.relevance}",
                )
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
        return bool(raw_job.title.strip() and raw_job.company.strip() and raw_job.url.strip() and raw_job.source_site.strip())

    def _apply_rule_filters(self, raw_job: RawJob) -> str | None:
        policy = RuntimeMatchingPolicy(self.runtime_matching_profile)
        combined_text = f"{raw_job.title} {raw_job.summary} {raw_job.description}".lower()
        salary_floor = parse_salary_floor(raw_job.salary_text)
        return policy.evaluate_prefilter_reason(
            text=combined_text,
            work_mode=raw_job.work_mode,
            salary_floor=salary_floor,
        )


def build_external_key(raw_job: RawJob) -> str:
    normalized = "|".join(
        [
            raw_job.title.strip().lower(),
            raw_job.company.strip().lower(),
            raw_job.location.strip().lower(),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
