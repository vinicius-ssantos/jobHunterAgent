import asyncio
import shutil
import sqlite3
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase

from job_hunter_agent.collectors.collector import (
    automation_result_to_text,
    build_available_file_paths,
    clean_linkedin_company,
    clean_linkedin_description,
    clean_linkedin_location,
    clean_linkedin_summary,
    clean_linkedin_title,
    JobCollectionService,
    build_external_key,
    contains_precision_term,
    extract_json_object,
    load_playwright_storage_state,
    merge_linkedin_card_with_detail,
    normalize_linkedin_card,
    normalize_linkedin_work_mode,
    parse_scoring_response,
    parse_salary_floor,
    infer_linkedin_company_from_summary,
    apply_linkedin_field_repair,
    is_suspicious_linkedin_company,
    is_suspicious_linkedin_location,
    parse_linkedin_field_repair_response,
    standardize_error_message,
    strip_linkedin_chrome_prefix,
    strip_title_prefix_from_location,
    should_enrich_linkedin_card,
    should_repair_linkedin_fields,
    summarize_linkedin_raw_card,
)
from job_hunter_agent.core.domain import JobPosting, RawJob, ScoredJob, SiteConfig
from job_hunter_agent.collectors.linkedin import LinkedInDeterministicCollector
from job_hunter_agent.collectors.portal_collectors import (
    BrowserUseSiteCollector,
    DefaultPortalCollectorAdapter,
    GupyCollectorAdapter,
    IndeedCollectorAdapter,
    LinkedInCollectorAdapter,
)
from job_hunter_agent.core.matching import MatchingCriteria, build_matching_criteria
from job_hunter_agent.core.runtime_matching import RuntimeLinkedInPrecisionGate, RuntimeMatchingProfile
from job_hunter_agent.infrastructure.repository import SqliteJobRepository
from job_hunter_agent.llm.scoring import HybridJobScorer
from job_hunter_agent.core.settings import Settings
from tests.tmp_workspace import prepare_workspace_tmp_dir


class FakeSiteCollector:
    async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
        return [
            RawJob(
                title="Senior Kotlin Engineer",
                company="ACME",
                location="Brasil",
                work_mode="remoto",
                salary_text="Nao informado",
                url="https://example.com/job-1",
                source_site=site.name,
                summary="Backend role com Kotlin e Spring.",
                description="Projeto backend distribuido.",
            ),
            RawJob(
                title="Junior PHP Developer",
                company="Legacy Corp",
                location="Brasil",
                work_mode="presencial",
                salary_text="Nao informado",
                url="https://example.com/job-2",
                source_site=site.name,
                summary="Role junior com PHP.",
                description="Atuacao presencial com PHP.",
            ),
        ]


class InvalidFakeSiteCollector:
    async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
        return [
            RawJob(
                title="",
                company="",
                location="Brasil",
                work_mode="remoto",
                salary_text="Nao informado",
                url="",
                source_site=site.name,
                summary="Resumo",
                description="Descricao",
            )
        ]


class FailingSiteCollector:
    async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
        raise RuntimeError("portal indisponivel")


class SlowSiteCollector:
    async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
        import asyncio

        await asyncio.sleep(0.05)
        return []


class FakeScorer:
    def score(self, raw_job: RawJob, criteria: MatchingCriteria) -> ScoredJob:
        if "PHP" in raw_job.title:
            return ScoredJob(relevance=2, rationale="Tecnologia excluida.", accepted=False)
        return ScoredJob(relevance=8, rationale="Bom fit tecnico.", accepted=True)


class FlakyScorer:
    def score(self, raw_job: RawJob, criteria: MatchingCriteria) -> ScoredJob:
        if "Kotlin" in raw_job.title:
            raise RuntimeError("modelo indisponivel")
        return ScoredJob(relevance=7, rationale="Fallback valido.", accepted=True)


class FailingIfCalledScorer:
    def score(self, raw_job: RawJob, criteria: MatchingCriteria) -> ScoredJob:
        raise AssertionError("scorer nao deveria ser chamado para vaga duplicada")


class MixedRawSiteCollector:
    async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
        return [
            RawJob(
                title="Senior Kotlin Engineer",
                company="ACME",
                location="Brasil",
                work_mode="remoto",
                salary_text="Nao informado",
                url="https://example.com/job-1",
                source_site=site.name,
                summary="Backend role com Kotlin e Spring.",
                description="Projeto backend distribuido.",
            ),
            RawJob(
                title="Senior Java Engineer",
                company="ACME",
                location="Brasil",
                work_mode="remoto",
                salary_text="Nao informado",
                url="https://example.com/job-3",
                source_site=site.name,
                summary="Backend role com Java e Spring.",
                description="Projeto backend distribuido.",
            ),
        ]


class JobCollectionServiceTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = prepare_workspace_tmp_dir("collector")
        self.db_path = self.temp_dir / "jobs.db"
        self.repository = SqliteJobRepository(self.db_path)
        self.settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            linkedin_precision_gate_enabled=False,
            sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
        )
        self.matching_criteria = build_matching_criteria(
            profile_text=self.settings.profile_text,
            include_keywords=self.settings.include_keywords,
            exclude_keywords=self.settings.exclude_keywords,
            accepted_work_modes=self.settings.accepted_work_modes,
            minimum_salary_brl=self.settings.minimum_salary_brl,
            minimum_relevance=self.settings.minimum_relevance,
            relaxed_matching_for_testing=self.settings.relaxed_matching_for_testing,
            relaxed_testing_profile_hint=self.settings.relaxed_testing_profile_hint,
            relaxed_testing_remove_exclude_keywords=self.settings.relaxed_testing_remove_exclude_keywords,
            relaxed_testing_minimum_relevance=self.settings.relaxed_testing_minimum_relevance,
        )

    async def asyncTearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_collect_new_jobs_filters_and_saves_only_relevant_jobs(self) -> None:
        service = JobCollectionService(
            settings=self.settings,
            matching_criteria=self.matching_criteria,
            repository=self.repository,
            site_collector=FakeSiteCollector(),
            scorer=FakeScorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Kotlin Engineer")
        self.assertTrue(self.repository.job_exists(jobs[0].url, jobs[0].external_key))

    async def test_collect_new_jobs_filters_out_wrong_work_mode_before_scoring(self) -> None:
        filtered_settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            accepted_work_modes=("remoto",),
            linkedin_precision_gate_enabled=False,
            sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
        )
        service = JobCollectionService(
            settings=filtered_settings,
            matching_criteria=build_matching_criteria(
                profile_text=filtered_settings.profile_text,
                include_keywords=filtered_settings.include_keywords,
                exclude_keywords=filtered_settings.exclude_keywords,
                accepted_work_modes=filtered_settings.accepted_work_modes,
                minimum_salary_brl=filtered_settings.minimum_salary_brl,
                minimum_relevance=filtered_settings.minimum_relevance,
                relaxed_matching_for_testing=filtered_settings.relaxed_matching_for_testing,
                relaxed_testing_profile_hint=filtered_settings.relaxed_testing_profile_hint,
                relaxed_testing_remove_exclude_keywords=filtered_settings.relaxed_testing_remove_exclude_keywords,
                relaxed_testing_minimum_relevance=filtered_settings.relaxed_testing_minimum_relevance,
            ),
            repository=self.repository,
            site_collector=FakeSiteCollector(),
            scorer=FakeScorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].work_mode, "remoto")

    async def test_collect_new_jobs_report_contains_cycle_counts(self) -> None:
        service = JobCollectionService(
            settings=self.settings,
            matching_criteria=self.matching_criteria,
            repository=self.repository,
            site_collector=FakeSiteCollector(),
            scorer=FakeScorer(),
        )

        report = await service.collect_new_jobs_report()

        self.assertEqual(report.jobs_seen, 2)
        self.assertEqual(report.jobs_saved, 1)
        self.assertEqual(report.errors, 0)
        self.assertEqual(len(report.jobs), 1)

    async def test_collect_new_jobs_discards_minimally_invalid_jobs(self) -> None:
        service = JobCollectionService(
            settings=self.settings,
            matching_criteria=self.matching_criteria,
            repository=self.repository,
            site_collector=InvalidFakeSiteCollector(),
            scorer=FakeScorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(jobs, [])

    async def test_collect_new_jobs_report_tracks_portal_failures(self) -> None:
        service = JobCollectionService(
            settings=self.settings,
            matching_criteria=self.matching_criteria,
            repository=self.repository,
            site_collector=FailingSiteCollector(),
            scorer=FakeScorer(),
        )

        report = await service.collect_new_jobs_report()

        self.assertEqual(report.jobs_seen, 0)
        self.assertEqual(report.jobs_saved, 0)
        self.assertEqual(report.errors, 1)

    async def test_collect_new_jobs_report_times_out_slow_portal(self) -> None:
        timeout_settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            portal_collection_timeout_seconds=0,
            linkedin_precision_gate_enabled=False,
            sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
        )
        service = JobCollectionService(
            settings=timeout_settings,
            matching_criteria=build_matching_criteria(
                profile_text=timeout_settings.profile_text,
                include_keywords=timeout_settings.include_keywords,
                exclude_keywords=timeout_settings.exclude_keywords,
                accepted_work_modes=timeout_settings.accepted_work_modes,
                minimum_salary_brl=timeout_settings.minimum_salary_brl,
                minimum_relevance=timeout_settings.minimum_relevance,
                relaxed_matching_for_testing=timeout_settings.relaxed_matching_for_testing,
                relaxed_testing_profile_hint=timeout_settings.relaxed_testing_profile_hint,
                relaxed_testing_remove_exclude_keywords=timeout_settings.relaxed_testing_remove_exclude_keywords,
                relaxed_testing_minimum_relevance=timeout_settings.relaxed_testing_minimum_relevance,
            ),
            repository=self.repository,
            site_collector=SlowSiteCollector(),
            scorer=FakeScorer(),
        )

        report = await service.collect_new_jobs_report()

        self.assertEqual(report.jobs_seen, 0)
        self.assertEqual(report.jobs_saved, 0)
        self.assertEqual(report.errors, 1)
        with sqlite3.connect(self.db_path) as connection:
            last_log = connection.execute(
                "SELECT message FROM collection_logs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertIsNotNone(last_log)
        self.assertIn("timeout apos 0s", last_log[0])

    async def test_collect_new_jobs_skips_scoring_errors_and_keeps_valid_jobs(self) -> None:
        service = JobCollectionService(
            settings=self.settings,
            matching_criteria=self.matching_criteria,
            repository=self.repository,
            site_collector=MixedRawSiteCollector(),
            scorer=FlakyScorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Java Engineer")

    async def test_collect_new_jobs_report_logs_duplicates_in_portal_summary(self) -> None:
        service = JobCollectionService(
            settings=self.settings,
            matching_criteria=self.matching_criteria,
            repository=self.repository,
            site_collector=FakeSiteCollector(),
            scorer=FakeScorer(),
        )

        first_report = await service.collect_new_jobs_report()
        second_report = await service.collect_new_jobs_report()

        self.assertEqual(first_report.jobs_saved, 1)
        self.assertEqual(second_report.jobs_saved, 0)
        with sqlite3.connect(self.db_path) as connection:
            last_log = connection.execute(
                "SELECT message FROM collection_logs WHERE level = 'info' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertIsNotNone(last_log)
        self.assertIn("duplicadas=2", last_log[0])

    async def test_collect_new_jobs_skips_known_raw_jobs_before_scoring(self) -> None:
        existing = RawJob(
            title="Senior Kotlin Engineer",
            company="ACME",
            location="Brasil",
            work_mode="remoto",
            salary_text="Nao informado",
            url="https://example.com/job-1",
            source_site="LinkedIn",
            summary="Backend role com Kotlin e Spring.",
            description="Projeto backend distribuido.",
        )
        self.repository.save_new_jobs(
            [
                JobPosting(
                    title=existing.title,
                    company=existing.company,
                    location=existing.location,
                    work_mode=existing.work_mode,
                    salary_text=existing.salary_text,
                    url=existing.url,
                    source_site=existing.source_site,
                    summary=existing.summary,
                    relevance=8,
                    rationale="Ja existente",
                    external_key=build_external_key(existing),
                )
            ]
        )
        service = JobCollectionService(
            settings=self.settings,
            matching_criteria=self.matching_criteria,
            repository=self.repository,
            site_collector=FakeSiteCollector(),
            scorer=FailingIfCalledScorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(jobs, [])

    async def test_collect_new_jobs_remembers_discarded_jobs_to_skip_next_cycle(self) -> None:
        service = JobCollectionService(
            settings=self.settings,
            matching_criteria=self.matching_criteria,
            repository=self.repository,
            site_collector=FakeSiteCollector(),
            scorer=FakeScorer(),
        )

        first_jobs = await service.collect_new_jobs()
        second_jobs = await service.collect_new_jobs()

        self.assertEqual(len(first_jobs), 1)
        self.assertEqual(second_jobs, [])
        self.assertTrue(self.repository.seen_job_exists("https://example.com/job-2", build_external_key(
            RawJob(
                title="Junior PHP Developer",
                company="Legacy Corp",
                location="Brasil",
                work_mode="presencial",
                salary_text="Nao informado",
                url="https://example.com/job-2",
                source_site="LinkedIn",
                summary="Role junior com PHP.",
                description="Atuacao presencial com PHP.",
            )
        )))

    async def test_collect_new_jobs_discards_probable_external_apply_before_scoring(self) -> None:
        class _Collector:
            async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
                return [
                    RawJob(
                        title="Desenvolvedor Java Pleno",
                        company="ACME",
                        location="Brasil",
                        work_mode="remoto",
                        salary_text="Nao informado",
                        url="https://www.linkedin.com/jobs/view/123/",
                        source_site="LinkedIn",
                        summary="Respostas gerenciadas fora do LinkedIn",
                        description="Candidate-se no site da empresa",
                    )
                ]

        service = JobCollectionService(
            settings=self.settings,
            matching_criteria=self.matching_criteria,
            repository=self.repository,
            site_collector=_Collector(),
            scorer=FailingIfCalledScorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(jobs, [])
        self.assertTrue(
            self.repository.seen_job_exists(
                "https://www.linkedin.com/jobs/view/123/",
                build_external_key(
                    RawJob(
                        title="Desenvolvedor Java Pleno",
                        company="ACME",
                        location="Brasil",
                        work_mode="remoto",
                        salary_text="Nao informado",
                        url="https://www.linkedin.com/jobs/view/123/",
                        source_site="LinkedIn",
                        summary="Respostas gerenciadas fora do LinkedIn",
                        description="Candidate-se no site da empresa",
                    )
                ),
            )
        )

    async def test_collect_new_jobs_precision_gate_blocks_non_java_business_roles(self) -> None:
        class _Collector:
            async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
                return [
                    RawJob(
                        title="Program Manager",
                        company="ACME",
                        location="Brasil",
                        work_mode="remoto",
                        salary_text="Nao informado",
                        url="https://www.linkedin.com/jobs/view/999/",
                        source_site="LinkedIn",
                        summary="Program manager for growth and operations",
                        description="business development and account executive operations",
                    )
                ]

        gate_settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            linkedin_precision_gate_enabled=True,
            sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
        )
        service = JobCollectionService(
            settings=gate_settings,
            runtime_matching_profile=RuntimeMatchingProfile(
                candidate_summary="Backend Java",
                include_keywords=("java",),
                exclude_keywords=(),
                accepted_work_modes=(),
                minimum_salary_brl=0,
                minimum_relevance=6,
                linkedin_precision_gate=RuntimeLinkedInPrecisionGate(
                    required_terms=("java",),
                    any_terms=("backend", "developer"),
                    blocked_terms=("program manager", "operations", "sales"),
                ),
            ),
            repository=self.repository,
            site_collector=_Collector(),
            scorer=FailingIfCalledScorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(jobs, [])
        self.assertTrue(
            self.repository.seen_job_exists(
                "https://www.linkedin.com/jobs/view/999/",
                build_external_key(
                    RawJob(
                        title="Program Manager",
                        company="ACME",
                        location="Brasil",
                        work_mode="remoto",
                        salary_text="Nao informado",
                        url="https://www.linkedin.com/jobs/view/999/",
                        source_site="LinkedIn",
                        summary="Program manager for growth and operations",
                        description="business development and account executive operations",
                    )
                ),
            )
        )

    async def test_collect_new_jobs_precision_gate_uses_configured_terms_instead_of_java_hardcode(self) -> None:
        class _Collector:
            async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
                return [
                    RawJob(
                        title="Python Backend Developer",
                        company="ACME",
                        location="Brasil",
                        work_mode="remoto",
                        salary_text="Nao informado",
                        url="https://www.linkedin.com/jobs/view/1000/",
                        source_site="LinkedIn",
                        summary="Backend role com Python e APIs.",
                        description="Desenvolvimento de servicos backend.",
                    )
                ]

        class _Scorer:
            def score(self, raw_job: RawJob, runtime_matching_profile: RuntimeMatchingProfile) -> ScoredJob:
                return ScoredJob(relevance=8, rationale="fit python backend", accepted=True)

        gate_settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            linkedin_precision_gate_enabled=True,
            sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
        )
        service = JobCollectionService(
            settings=gate_settings,
            runtime_matching_profile=RuntimeMatchingProfile(
                candidate_summary="Backend Python",
                include_keywords=("python",),
                exclude_keywords=(),
                accepted_work_modes=(),
                minimum_salary_brl=0,
                minimum_relevance=6,
                linkedin_precision_gate=RuntimeLinkedInPrecisionGate(any_terms=("python", "backend")),
            ),
            repository=self.repository,
            site_collector=_Collector(),
            scorer=_Scorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Python Backend Developer")

    async def test_collect_new_jobs_precision_gate_does_not_match_short_terms_inside_words(self) -> None:
        class _Collector:
            async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
                return [
                    RawJob(
                        title="Django Backend Developer",
                        company="ACME",
                        location="Brasil",
                        work_mode="remoto",
                        salary_text="Nao informado",
                        url="https://www.linkedin.com/jobs/view/1001/",
                        source_site="LinkedIn",
                        summary="Cargo backend com Django.",
                        description="Desenvolvimento de APIs.",
                    )
                ]

        gate_settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            linkedin_precision_gate_enabled=True,
            sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
        )
        service = JobCollectionService(
            settings=gate_settings,
            runtime_matching_profile=RuntimeMatchingProfile(
                candidate_summary="Go backend",
                include_keywords=("go",),
                exclude_keywords=(),
                accepted_work_modes=(),
                minimum_salary_brl=0,
                minimum_relevance=6,
                linkedin_precision_gate=RuntimeLinkedInPrecisionGate(any_terms=("go",)),
            ),
            repository=self.repository,
            site_collector=_Collector(),
            scorer=FailingIfCalledScorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(jobs, [])


class PrecisionTermMatchingTests(TestCase):
    def test_contains_precision_term_matches_whole_short_token(self) -> None:
        self.assertTrue(contains_precision_term("Go backend developer", "go"))

    def test_contains_precision_term_does_not_match_inside_larger_words(self) -> None:
        self.assertFalse(contains_precision_term("Django backend cargo", "go"))

    def test_contains_precision_term_preserves_phrase_matching(self) -> None:
        self.assertTrue(contains_precision_term("Senior software engineer backend", "software engineer"))
        self.assertTrue(contains_precision_term("Business development manager", "business development"))


class ExternalKeyTests(TestCase):
    def test_build_available_file_paths_includes_relative_and_absolute_screenshots(self) -> None:
        paths = build_available_file_paths(Path(".browseruse"), limit=2)

        self.assertIn("./screenshot1.png", paths)
        self.assertIn("./screenshot2.png", paths)
        self.assertTrue(any(path.endswith("screenshot1.png") and path != "./screenshot1.png" for path in paths))

    def test_automation_result_to_text_accepts_plain_string(self) -> None:
        self.assertEqual(automation_result_to_text('{"jobs": []}'), '{"jobs": []}')

    def test_automation_result_to_text_uses_final_result_when_available(self) -> None:
        class FakeAgentHistoryList:
            def final_result(self) -> str:
                return '{"jobs": [{"title": "Kotlin Engineer"}]}'

        self.assertEqual(
            automation_result_to_text(FakeAgentHistoryList()),
            '{"jobs": [{"title": "Kotlin Engineer"}]}',
        )

    def test_extract_json_object_reads_result_from_history_like_object(self) -> None:
        class FakeAgentHistoryList:
            def final_result(self) -> str:
                return '{"jobs": [{"title": "Kotlin Engineer", "url": "https://example.com"}]}'

        payload = extract_json_object(FakeAgentHistoryList())

        self.assertEqual(payload["jobs"][0]["title"], "Kotlin Engineer")

    def test_build_external_key_is_stable(self) -> None:
        raw_job = RawJob(
            title="Senior Kotlin Engineer",
            company="ACME",
            location="Brasil",
            work_mode="remoto",
            salary_text="Nao informado",
            url="https://example.com/job-1",
            source_site="LinkedIn",
            summary="Resumo",
            description="Descricao",
        )

        first = build_external_key(raw_job)
        second = build_external_key(raw_job)

        self.assertEqual(first, second)

    def test_parse_salary_floor_returns_first_numeric_value(self) -> None:
        self.assertEqual(parse_salary_floor("R$ 12.000 - R$ 15.000"), 12000)
        self.assertIsNone(parse_salary_floor("Nao informado"))

    def test_standardize_error_message(self) -> None:
        self.assertEqual(
            standardize_error_message("erro de coleta", "LinkedIn", "timeout"),
            "erro de coleta | site=LinkedIn | detalhe=timeout",
        )

    def test_summarize_linkedin_raw_card_keeps_only_relevant_debug_fields(self) -> None:
        summary = summarize_linkedin_raw_card(
            {
                "title": "Desenvolvedor Java",
                "company": "",
                "location": "",
                "raw_company_candidates": "Stefanini Brasil",
                "raw_metadata_candidates": "Osasco, São Paulo, Brasil (Híbrido)",
                "detail_company_candidates": "Stefanini Brasil",
                "detail_metadata_candidates": "Osasco, São Paulo, Brasil (Híbrido)",
                "raw_lines": "Desenvolvedor Java | Stefanini Brasil | Osasco, São Paulo, Brasil (Híbrido)",
            }
        )

        self.assertIn("title='Desenvolvedor Java'", summary)
        self.assertIn("raw_company_candidates='Stefanini Brasil'", summary)
        self.assertIn("raw_metadata_candidates='Osasco, São Paulo, Brasil (Híbrido)'", summary)
        self.assertIn("detail_company_candidates='Stefanini Brasil'", summary)

    def test_load_playwright_storage_state_normalizes_partition_key(self) -> None:
        temp_dir = prepare_workspace_tmp_dir("storage")
        temp_path = temp_dir / "storage-state.json"
        temp_path.write_text(
            """
            {
              "cookies": [
                {
                  "name": "li_at",
                  "value": "token",
                  "domain": ".linkedin.com",
                  "path": "/",
                  "expires": -1,
                  "httpOnly": true,
                  "secure": true,
                  "sameSite": "Lax",
                  "partitionKey": {
                    "topLevelSite": "https://linkedin.com",
                    "hasCrossSiteAncestor": true
                  }
                }
              ],
              "origins": []
            }
            """.strip(),
            encoding="utf-8",
        )
        try:
            state = load_playwright_storage_state(temp_path)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(state["cookies"][0]["partitionKey"], "https://linkedin.com")

    def test_parse_scoring_response_accepts_valid_json(self) -> None:
        score = parse_scoring_response('{"relevance": 8, "rationale": "Bom fit tecnico."}', 6)

        self.assertEqual(score.relevance, 8)
        self.assertEqual(score.rationale, "Bom fit tecnico.")
        self.assertTrue(score.accepted)

    def test_parse_scoring_response_rejects_invalid_json(self) -> None:
        score = parse_scoring_response("resposta sem formato", 6)

        self.assertEqual(score.relevance, 1)
        self.assertIn("sem JSON valido", score.rationale)
        self.assertFalse(score.accepted)

    def test_normalize_linkedin_card_cleans_polluted_fields(self) -> None:
        normalized = normalize_linkedin_card(
            {
                "title": "Desenvolvedor Java \n    \n    \n\nDesenvolvedor Java with verification",
                "company": (
                    "Desenvolvedor Java Desenvolvedor Java with verification "
                    "Verx Tecnologia e Inovação São Paulo, São Paulo, Brasil (Híbrido) "
                    "Avaliando candidaturas Visualizado Promovida Candidatura simplificada"
                ),
                "location": "São Paulo, São Paulo, Brasil (Híbrido)",
                "work_mode": "",
                "salary_text": "",
                "url": "https://www.linkedin.com/jobs/view/123",
                "summary": (
                    "Desenvolvedor Java Verx Tecnologia e Inovação São Paulo, São Paulo, Brasil (Híbrido) "
                    "Avaliando candidaturas Promovida Candidatura simplificada"
                ),
                "description": (
                    "Desenvolvedor Java Verx Tecnologia e Inovação São Paulo, São Paulo, Brasil (Híbrido) "
                    "Avaliando candidaturas Visualizado Promovida Candidatura simplificada 63 candidaturas há 2 dias"
                ),
            }
        )

        self.assertEqual(normalized["title"], "Desenvolvedor Java")
        self.assertEqual(normalized["company"], "Verx Tecnologia e Inovação")
        self.assertEqual(normalized["location"], "São Paulo, São Paulo, Brasil (Híbrido)")
        self.assertEqual(normalized["work_mode"], "hibrido")
        self.assertNotIn("Promovida", normalized["summary"])
        self.assertNotIn("Candidatura simplificada", normalized["description"])

    def test_linkedin_helpers_clean_company_location_and_work_mode(self) -> None:
        self.assertEqual(clean_linkedin_title("Engenheiro de Software with verification"), "Engenheiro de Software")
        self.assertEqual(
            clean_linkedin_title("AI Agent Engineer Jr/Pl AI Agent Engineer Jr/Pl"),
            "AI Agent Engineer Jr/Pl",
        )
        self.assertEqual(
            clean_linkedin_title("Mid/Senior iOS DeveloperMid/Senior iOS Developer"),
            "Mid/Senior iOS Developer",
        )
        self.assertEqual(
            clean_linkedin_company(
                "Pessoa Desenvolvedora Backend Java PL Pessoa Desenvolvedora Backend Java PL Bradesco Osasco,"
            ),
            "Bradesco Osasco,",
        )
        self.assertEqual(
            clean_linkedin_location("São Paulo, São Paulo, Brasil (Híbrido) · há 2 dias"),
            "São Paulo, São Paulo, Brasil (Híbrido)",
        )
        self.assertEqual(normalize_linkedin_work_mode("", "São Paulo, São Paulo, Brasil (Híbrido)"), "hibrido")
        self.assertEqual(clean_linkedin_summary("Promovida Candidatura simplificada Java Backend"), "Java Backend")
        self.assertEqual(clean_linkedin_description("Visualizado há 2 dias 63 candidaturas Kotlin"), "Kotlin")

    def test_normalize_linkedin_card_preserves_location_when_card_has_lines(self) -> None:
        normalized = normalize_linkedin_card(
            {
                "title": "Pessoa Desenvolvedora Backend Java PL",
                "company": "Bradesco",
                "location": "Osasco, São Paulo, Brasil (Híbrido)",
                "work_mode": "",
                "salary_text": "",
                "url": "https://www.linkedin.com/jobs/view/456",
                "summary": "Pessoa Desenvolvedora Backend Java PL Bradesco Osasco, São Paulo, Brasil (Híbrido)",
                "description": "Pessoa Desenvolvedora Backend Java PL Bradesco Osasco, São Paulo, Brasil (Híbrido)",
            }
        )

        self.assertEqual(normalized["company"], "Bradesco")
        self.assertEqual(normalized["location"], "Osasco, São Paulo, Brasil (Híbrido)")
        self.assertEqual(normalized["work_mode"], "hibrido")

    def test_normalize_linkedin_card_uses_location_field_as_company_fallback(self) -> None:
        normalized = normalize_linkedin_card(
            {
                "title": "Desenvolvedor(a) Java",
                "company": "",
                "location": "Stefanini Brasil",
                "work_mode": "hibrido",
                "salary_text": "",
                "url": "https://www.linkedin.com/jobs/view/789",
                "summary": "Desenvolvedor(a) Java Stefanini Brasil",
                "description": "Desenvolvedor(a) Java Stefanini Brasil",
            }
        )

        self.assertEqual(normalized["company"], "Stefanini Brasil", normalized)
        self.assertEqual(normalized["location"], "")

    def test_clean_linkedin_location_rejects_company_like_text(self) -> None:
        self.assertEqual(clean_linkedin_location("Stefanini Brasil"), "")

    def test_clean_linkedin_location_extracts_location_from_summary_blob(self) -> None:
        self.assertEqual(
            clean_linkedin_location(
                "Desenvolvedor(a) Java Desenvolvedor(a) Java with verification Stefanini Brasil Osasco, São Paulo, Brasil (Híbrido) Avaliando candidaturas"
            ),
            "Osasco, São Paulo, Brasil (Híbrido)",
        )

    def test_clean_linkedin_company_rejects_city_fragment(self) -> None:
        self.assertEqual(clean_linkedin_company("Osasco,"), "")

    def test_clean_linkedin_company_rejects_social_proof_segments(self) -> None:
        self.assertEqual(clean_linkedin_company("20 ex-funcionários trabalham aqui"), "")
        self.assertEqual(clean_linkedin_company("3 conexões trabalham aqui"), "")

    def test_clean_linkedin_company_strips_trailing_job_fragment(self) -> None:
        self.assertEqual(clean_linkedin_company("EY Desenvolvedor (a)"), "EY")
        self.assertEqual(
            clean_linkedin_company(
                "Grupo Boticário Pessoa Desenvolvedora Backend Java / Kotlin / Node.js III (E-commerce) Brasil"
            ),
            "Grupo Boticário",
        )

    def test_strip_title_prefix_from_location_removes_contaminated_title(self) -> None:
        self.assertEqual(
            strip_title_prefix_from_location(
                "Desenvolvedor Java São Paulo, São Paulo, Brasil", "Desenvolvedor Java"
            ),
            "São Paulo, São Paulo, Brasil",
        )

    def test_strip_title_prefix_from_location_removes_partial_title_suffix(self) -> None:
        self.assertEqual(
            strip_title_prefix_from_location(
                "Backend Java São Paulo, São Paulo, Brasil",
                "Desenvolvedor (a) Backend Java",
            ),
            "São Paulo, São Paulo, Brasil",
        )

    def test_infer_linkedin_company_from_summary_extracts_company_between_title_and_location(self) -> None:
        self.assertEqual(
            infer_linkedin_company_from_summary(
                "Desenvolvedor Java Stefanini Brasil Osasco, São Paulo, Brasil (Híbrido)",
                "Desenvolvedor Java",
                "Osasco, São Paulo, Brasil (Híbrido)",
            ),
            "Stefanini Brasil",
        )

    def test_strip_linkedin_chrome_prefix_removes_navigation_noise(self) -> None:
        self.assertEqual(
            strip_linkedin_chrome_prefix(
                "0 notificação Pular para conteúdo principal Início Minha rede Vagas Mensagens Notificações Eu Para negócios Reative Premium: 50% de desconto Verx Tecnologia e Inovação Desenvolvedor Java"
            ),
            "Verx Tecnologia e Inovação Desenvolvedor Java",
        )

    def test_infer_linkedin_company_from_summary_removes_linkedin_chrome_and_trailing_title(self) -> None:
        self.assertEqual(
            infer_linkedin_company_from_summary(
                "0 notificação Pular para conteúdo principal Início Minha rede Vagas Mensagens Notificações Eu Para negócios Reative Premium: 50% de desconto Verx Tecnologia e Inovação Desenvolvedor Java São Paulo, São Paulo, Brasil",
                "Desenvolvedor Java",
                "São Paulo, São Paulo, Brasil",
            ),
            "Verx Tecnologia e Inovação",
        )

    def test_is_suspicious_linkedin_company_flags_city_fragment(self) -> None:
        self.assertTrue(is_suspicious_linkedin_company("Osasco,", "Osasco, São Paulo, Brasil (Híbrido)"))
        self.assertFalse(
            is_suspicious_linkedin_company("Stefanini Brasil", "Osasco, São Paulo, Brasil (Híbrido)")
        )
        self.assertTrue(
            is_suspicious_linkedin_company(
                "Verx Tecnologia e Inovação Desenvolvedor Java",
                "São Paulo, São Paulo, Brasil",
                "Desenvolvedor Java",
            )
        )

    def test_is_suspicious_linkedin_location_flags_missing_and_contaminated_values(self) -> None:
        self.assertTrue(is_suspicious_linkedin_location("", "Desenvolvedor Java"))
        self.assertTrue(
            is_suspicious_linkedin_location(
                "Desenvolvedor Java São Paulo, São Paulo, Brasil", "Desenvolvedor Java"
            )
        )
        self.assertFalse(
            is_suspicious_linkedin_location("São Paulo, São Paulo, Brasil", "Desenvolvedor Java")
        )
        self.assertTrue(
            is_suspicious_linkedin_location(
                "de desconto Verx Tecnologia e Inovação Desenvolvedor Java São Paulo, São Paulo, Brasil",
                "Desenvolvedor Java",
                "Verx Tecnologia e Inovação",
            )
        )

    def test_normalize_linkedin_card_prefers_inferred_company_when_raw_company_looks_like_location(self) -> None:
        normalized = normalize_linkedin_card(
            {
                "title": "Desenvolvedor full stack",
                "company": "Osasco,",
                "location": "Osasco, Sao Paulo, Brasil (Hibrido)",
                "work_mode": "",
                "salary_text": "",
                "url": "https://www.linkedin.com/jobs/view/123",
                "summary": "Desenvolvedor full stack Stefanini Brasil Osasco, Sao Paulo, Brasil (Hibrido)",
                "description": "",
            }
        )

        self.assertEqual(normalized["company"], "Stefanini Brasil")
        self.assertEqual(normalized["location"], "Osasco, Sao Paulo, Brasil (Hibrido)")

    def test_normalize_linkedin_card_strips_title_suffix_from_company_and_location_noise(self) -> None:
        normalized = normalize_linkedin_card(
            {
                "title": "Desenvolvedor Java",
                "company": "Verx Tecnologia e Inovação Desenvolvedor Java",
                "location": "de desconto Verx Tecnologia e Inovação Desenvolvedor Java São Paulo, São Paulo, Brasil",
                "work_mode": "",
                "salary_text": "",
                "url": "https://www.linkedin.com/jobs/view/123",
                "summary": "Desenvolvedor Java Verx Tecnologia e Inovação São Paulo, São Paulo, Brasil",
                "description": "",
            }
        )

        self.assertEqual(normalized["company"], "Verx Tecnologia e Inovação")
        self.assertEqual(normalized["location"], "São Paulo, São Paulo, Brasil")

    def test_normalize_linkedin_card_strips_title_prefix_from_company(self) -> None:
        normalized = normalize_linkedin_card(
            {
                "title": "Desenvolvedor full stack",
                "company": "Desenvolvedor full stack Vivo (Telefônica Brasil)",
                "location": "São Paulo, Brasil (Híbrido)",
                "work_mode": "hibrido",
                "salary_text": "",
                "url": "https://www.linkedin.com/jobs/view/123",
                "summary": "Desenvolvedor full stack Vivo (Telefônica Brasil) São Paulo, Brasil (Híbrido)",
                "description": "",
            }
        )

        self.assertEqual(normalized["company"], "Vivo (Telefônica Brasil)")
        self.assertEqual(normalized["location"], "São Paulo, Brasil (Híbrido)")

    def test_normalize_linkedin_card_replaces_social_proof_company_with_inferred_company(self) -> None:
        normalized = normalize_linkedin_card(
            {
                "title": "Desenvolvedor Java Full Stack Pleno",
                "company": "20 ex-funcionários trabalham aqui",
                "location": "Brasil (Remoto)",
                "work_mode": "",
                "salary_text": "",
                "url": "https://www.linkedin.com/jobs/view/123",
                "summary": "Desenvolvedor Java Full Stack Pleno BRQ Digital Solutions Brasil (Remoto)",
                "description": "",
            }
        )

        self.assertEqual(normalized["company"], "BRQ Digital Solutions")
        self.assertEqual(normalized["location"], "Brasil (Remoto)")

    def test_normalize_linkedin_card_keeps_regional_location_and_cleans_company(self) -> None:
        normalized = normalize_linkedin_card(
            {
                "title": "Desenvolvedor full stack",
                "company": "Instituto de Pesquisas ELDORADO Desenvolvedor full stack",
                "location": "Campinas e RegiÃ£o",
                "work_mode": "",
                "salary_text": "",
                "url": "https://www.linkedin.com/jobs/view/123",
                "summary": "Instituto de Pesquisas ELDORADO Desenvolvedor full stack Campinas e RegiÃ£o",
                "description": "",
            }
        )

        self.assertEqual(normalized["company"], "Instituto de Pesquisas ELDORADO")
        self.assertEqual(normalized["location"], "Campinas e RegiÃ£o")

    def test_normalize_linkedin_card_cleans_truncated_premium_prefix_and_role_suffix(self) -> None:
        normalized = normalize_linkedin_card(
            {
                "title": "Desenvolvedor FullStack Pleno",
                "company": "mium: 50% de desconto btime Desenvolvedor FullStack Pleno",
                "location": "mium: 50% de desconto btime Desenvolvedor FullStack Pleno SÃ£o Paulo, SÃ£o Paulo, Brasil",
                "work_mode": "",
                "salary_text": "",
                "url": "https://www.linkedin.com/jobs/view/123",
                "summary": "mium: 50% de desconto btime Desenvolvedor FullStack Pleno SÃ£o Paulo, SÃ£o Paulo, Brasil",
                "description": "",
            }
        )

        self.assertEqual(normalized["company"], "btime")
        self.assertEqual(normalized["location"], "SÃ£o Paulo, SÃ£o Paulo, Brasil")

    def test_normalize_linkedin_card_cleans_ai_stealth_company_from_title_pollution(self) -> None:
        normalized = normalize_linkedin_card(
            {
                "title": "Full Stack Engineer",
                "company": "AI Stealth Full Stack Engineer Brasil",
                "location": "",
                "work_mode": "",
                "salary_text": "",
                "url": "https://www.linkedin.com/jobs/view/123",
                "summary": "AI Stealth Full Stack Engineer Brasil",
                "description": "",
            }
        )

        self.assertEqual(normalized["company"], "AI Stealth")

    def test_normalize_linkedin_card_strips_title_pollution_from_company_before_location(self) -> None:
        normalized = normalize_linkedin_card(
            {
                "title": "Pessoa Desenvolvedora Backend Java / Kotlin / Node.js III (E-commerce)",
                "company": (
                    "Grupo Boticário Pessoa Desenvolvedora Backend Java / Kotlin / Node.js III (E-commerce) Brasil"
                ),
                "location": "Remoto",
                "work_mode": "",
                "salary_text": "",
                "url": "https://www.linkedin.com/jobs/view/123",
                "summary": (
                    "Pessoa Desenvolvedora Backend Java / Kotlin / Node.js III (E-commerce) "
                    "Grupo Boticário Brasil (Remoto)"
                ),
                "description": "",
            }
        )

        self.assertEqual(normalized["company"], "Grupo Boticário")
        self.assertEqual(normalized["location"], "Remoto")

    def test_should_repair_linkedin_fields_for_suspicious_company_or_location(self) -> None:
        self.assertTrue(
            should_repair_linkedin_fields(
                {"title": "Desenvolvedor Java", "company": "Osasco,", "location": "Osasco, São Paulo, Brasil"}
            )
        )
        self.assertFalse(
            should_repair_linkedin_fields(
                {
                    "title": "Desenvolvedor Java",
                    "company": "Verx Tecnologia e Inovação",
                    "location": "São Paulo, São Paulo, Brasil",
                }
            )
        )

    def test_parse_linkedin_field_repair_response_requires_confidence(self) -> None:
        self.assertEqual(
            parse_linkedin_field_repair_response(
                '{"company":"Verx Tecnologia e Inovação","location":"São Paulo, São Paulo, Brasil","confidence":8,"rationale":"coerente"}'
            ),
            {
                "company": "Verx Tecnologia e Inovação",
                "location": "São Paulo, São Paulo, Brasil",
                "rationale": "coerente",
            },
        )
        self.assertEqual(
            parse_linkedin_field_repair_response(
                '{"company":"Verx Tecnologia e Inovação","location":"São Paulo, São Paulo, Brasil","confidence":4}'
            ),
            {},
        )

    def test_apply_linkedin_field_repair_only_overwrites_suspicious_values(self) -> None:
        repaired = apply_linkedin_field_repair(
            {
                "title": "Desenvolvedor Java",
                "company": "Osasco,",
                "location": "Desenvolvedor Java São Paulo, São Paulo, Brasil",
            },
            {
                "company": "Verx Tecnologia e Inovação",
                "location": "São Paulo, São Paulo, Brasil",
            },
        )

        self.assertEqual(repaired["company"], "Verx Tecnologia e Inovação")
        self.assertEqual(repaired["location"], "São Paulo, São Paulo, Brasil")

    def test_should_enrich_linkedin_card_requires_detail_when_company_or_location_is_missing(self) -> None:
        self.assertTrue(should_enrich_linkedin_card({"company": "", "location": "Osasco, São Paulo, Brasil (Híbrido)"}))
        self.assertTrue(should_enrich_linkedin_card({"company": "Stefanini Brasil", "location": ""}))
        self.assertFalse(
            should_enrich_linkedin_card(
                {"company": "Stefanini Brasil", "location": "Osasco, São Paulo, Brasil (Híbrido)"}
            )
        )

    def test_merge_linkedin_card_with_detail_fills_missing_company_and_location(self) -> None:
        merged = merge_linkedin_card_with_detail(
            {
                "title": "Desenvolvedor Java",
                "company": "",
                "location": "",
                "summary": "Desenvolvedor Java",
            },
            {
                "title": "Desenvolvedor Java",
                "company": "Stefanini Brasil",
                "location": "Osasco, São Paulo, Brasil (Híbrido)",
                "summary": "Desenvolvedor Java Stefanini Brasil Osasco, São Paulo, Brasil (Híbrido)",
                "raw_company_candidates": "Stefanini Brasil",
                "raw_metadata_candidates": "Osasco, São Paulo, Brasil (Híbrido)",
            },
        )

        self.assertEqual(merged["company"], "Stefanini Brasil")
        self.assertEqual(merged["location"], "Osasco, São Paulo, Brasil (Híbrido)")
        self.assertEqual(
            merged["summary"], "Desenvolvedor Java Stefanini Brasil Osasco, São Paulo, Brasil (Híbrido)"
        )
        self.assertEqual(merged["detail_company_candidates"], "Stefanini Brasil")
        self.assertEqual(merged["detail_metadata_candidates"], "Osasco, São Paulo, Brasil (Híbrido)")
        self.assertIn("Stefanini Brasil", merged["detail_summary"])


class BrowserUseSiteCollectorAdapterTests(TestCase):
    def test_linkedin_collect_cards_across_pages_accumulates_until_limit(self) -> None:
        class FakePage:
            def __init__(self) -> None:
                self.waited_selectors: list[str] = []
                self.waited_timeouts: list[int] = []

            async def wait_for_selector(self, selector: str, timeout: int = 0) -> None:
                self.waited_selectors.append(selector)

            async def wait_for_timeout(self, timeout: int) -> None:
                self.waited_timeouts.append(timeout)

        collector = LinkedInDeterministicCollector(
            storage_state_path=Path("dummy.json"),
            headless=True,
            max_pages_per_cycle=3,
        )
        page = FakePage()
        extracted = [
            [{"url": "https://www.linkedin.com/jobs/view/1", "title": "Um"}],
            [{"url": "https://www.linkedin.com/jobs/view/2", "title": "Dois"}],
        ]

        async def fake_extract_visible_cards(current_page, max_jobs: int) -> list[dict[str, str]]:
            return extracted.pop(0)

        moves = [True, False]

        async def fake_go_to_next_results_page(current_page, next_page_number: int) -> bool:
            return moves.pop(0)

        collector._dismiss_sign_in_modal = lambda current_page: asyncio.sleep(0)
        collector._stabilize_results_page = lambda current_page: asyncio.sleep(0)
        collector._extract_visible_cards = fake_extract_visible_cards
        collector._go_to_next_results_page = fake_go_to_next_results_page

        cards = asyncio.run(collector._collect_cards_across_pages(page, 5))

        self.assertEqual([card["url"] for card in cards], [
            "https://www.linkedin.com/jobs/view/1",
            "https://www.linkedin.com/jobs/view/2",
        ])
        self.assertEqual(page.waited_timeouts, [1500])

    def test_linkedin_collect_cards_across_pages_stops_at_max_pages(self) -> None:
        class FakePage:
            async def wait_for_selector(self, selector: str, timeout: int = 0) -> None:
                return None

            async def wait_for_timeout(self, timeout: int) -> None:
                return None

        collector = LinkedInDeterministicCollector(
            storage_state_path=Path("dummy.json"),
            headless=True,
            max_pages_per_cycle=1,
        )
        page = FakePage()

        async def fake_extract_visible_cards(current_page, max_jobs: int) -> list[dict[str, str]]:
            return [{"url": "https://www.linkedin.com/jobs/view/1", "title": "Um"}]

        async def fake_go_to_next_results_page(current_page, next_page_number: int) -> bool:
            raise AssertionError("nao deveria tentar proxima pagina")

        collector._dismiss_sign_in_modal = lambda current_page: asyncio.sleep(0)
        collector._stabilize_results_page = lambda current_page: asyncio.sleep(0)
        collector._extract_visible_cards = fake_extract_visible_cards
        collector._go_to_next_results_page = fake_go_to_next_results_page

        cards = asyncio.run(collector._collect_cards_across_pages(page, 5))

        self.assertEqual(len(cards), 1)

    def test_linkedin_collect_cards_across_pages_always_starts_from_first_page_and_clicks_forward(self) -> None:
        class FakePage:
            def __init__(self) -> None:
                self.waited_timeouts: list[int] = []

            async def wait_for_selector(self, selector: str, timeout: int = 0) -> None:
                return None

            async def wait_for_timeout(self, timeout: int) -> None:
                self.waited_timeouts.append(timeout)

        collector = LinkedInDeterministicCollector(
            storage_state_path=Path("dummy.json"),
            headless=True,
            max_pages_per_cycle=2,
            max_page_depth=6,
        )
        page = FakePage()
        visited_pages: list[int] = []

        async def fake_extract_visible_cards(current_page, max_jobs: int) -> list[dict[str, str]]:
            return [{"url": f"https://www.linkedin.com/jobs/view/{len(visited_pages)+10}", "title": "Nova"}]

        async def fake_go_to_next_results_page(current_page, next_page_number: int) -> bool:
            visited_pages.append(next_page_number)
            return True

        collector._dismiss_sign_in_modal = lambda current_page: asyncio.sleep(0)
        collector._stabilize_results_page = lambda current_page: asyncio.sleep(0)
        collector._extract_visible_cards = fake_extract_visible_cards
        collector._go_to_next_results_page = fake_go_to_next_results_page

        cards = asyncio.run(collector._collect_cards_across_pages(page, 5))

        self.assertEqual(len(cards), 2)
        self.assertEqual(visited_pages, [2])

    def test_linkedin_collect_cards_across_pages_stops_after_consecutive_duplicate_pages(self) -> None:
        class FakePage:
            async def wait_for_selector(self, selector: str, timeout: int = 0) -> None:
                return None

            async def wait_for_timeout(self, timeout: int) -> None:
                return None

        collector = LinkedInDeterministicCollector(
            storage_state_path=Path("dummy.json"),
            headless=True,
            max_pages_per_cycle=4,
            duplicate_pages_stop_threshold=2,
        )
        page = FakePage()
        visited_pages: list[int] = []
        page_cards = [
            [{"url": "https://www.linkedin.com/jobs/view/1", "title": "Primeira"}],
            [{"url": "https://www.linkedin.com/jobs/view/1", "title": "Primeira"}],
            [{"url": "https://www.linkedin.com/jobs/view/1", "title": "Primeira"}],
        ]

        async def fake_extract_visible_cards(current_page, max_jobs: int) -> list[dict[str, str]]:
            return page_cards.pop(0)

        async def fake_go_to_next_results_page(current_page, next_page_number: int) -> bool:
            visited_pages.append(next_page_number)
            return True

        collector._dismiss_sign_in_modal = lambda current_page: asyncio.sleep(0)
        collector._stabilize_results_page = lambda current_page: asyncio.sleep(0)
        collector._extract_visible_cards = fake_extract_visible_cards
        collector._go_to_next_results_page = fake_go_to_next_results_page

        cards = asyncio.run(collector._collect_cards_across_pages(page, 10))

        self.assertEqual([card["url"] for card in cards], ["https://www.linkedin.com/jobs/view/1"])
        self.assertEqual(visited_pages, [2, 3])

    def test_linkedin_deterministic_collector_filters_known_cards_before_detail(self) -> None:
        collector = LinkedInDeterministicCollector(
            storage_state_path=Path("dummy.json"),
            headless=True,
            known_job_url_exists=lambda url: url == "https://www.linkedin.com/jobs/view/1",
        )

        filtered = collector._filter_known_cards(
            [
                {"url": "https://www.linkedin.com/jobs/view/1", "title": "Duplicada"},
                {"url": "https://www.linkedin.com/jobs/view/2", "title": "Nova"},
            ]
        )

        self.assertEqual([card["url"] for card in filtered], ["https://www.linkedin.com/jobs/view/2"])

    def test_linkedin_stabilize_results_page_scrolls_until_count_stops_changing(self) -> None:
        class FakePage:
            def __init__(self) -> None:
                self.states = [
                    {
                        "beforeCount": 4,
                        "count": 7,
                        "target": "lista+pagina",
                        "moved": True,
                        "pageAtEnd": False,
                        "listAtEnd": False,
                    },
                    {
                        "beforeCount": 7,
                        "count": 9,
                        "target": "lista+pagina",
                        "moved": True,
                        "pageAtEnd": True,
                        "listAtEnd": True,
                    },
                    {
                        "beforeCount": 9,
                        "count": 9,
                        "target": "lista+pagina",
                        "moved": False,
                        "pageAtEnd": True,
                        "listAtEnd": True,
                    },
                    {
                        "beforeCount": 9,
                        "count": 9,
                        "target": "lista+pagina",
                        "moved": False,
                        "pageAtEnd": True,
                        "listAtEnd": True,
                    },
                ]
                self.evaluate_calls = 0

            async def evaluate(self, script: str) -> dict[str, object]:
                self.evaluate_calls += 1
                return self.states.pop(0)

        collector = LinkedInDeterministicCollector(
            storage_state_path=Path("dummy.json"),
            headless=True,
            scroll_stabilization_passes=4,
        )
        page = FakePage()

        asyncio.run(collector._stabilize_results_page(page))

        self.assertEqual(page.evaluate_calls, 4)

    def test_linkedin_task_forbids_navigation_to_labels_or_jsonpath(self) -> None:
        adapter = LinkedInCollectorAdapter()

        task = adapter.build_task(SiteConfig(name="LinkedIn", search_url="https://example.com"), 5)

        self.assertIn("$.results[0]", task)
        self.assertIn("@aria-label", task)
        self.assertIn("Product Name", task)
        self.assertIn("Price", task)
        self.assertIn("Nunca navegue para '#'", task)
        self.assertIn("So use navigate se a string comecar com 'https://'", task)

    def test_collect_passes_non_linkedin_site_to_automation(self) -> None:
        class FakeAutomation:
            def __init__(self) -> None:
                self.captured_site_name = None

            async def run(self, task: str, site: SiteConfig | None = None) -> object:
                self.captured_site_name = site.name if site else None
                return '{"jobs": []}'

        automation = FakeAutomation()
        collector = BrowserUseSiteCollector(
            model_name="model",
            base_url="http://localhost:11434",
            automation=automation,
            portal_adapters=(GupyCollectorAdapter(), DefaultPortalCollectorAdapter()),
        )

        import asyncio

        jobs = asyncio.run(collector.collect(SiteConfig(name="Gupy", search_url="https://example.com"), 5))

        self.assertEqual(jobs, [])
        self.assertEqual(automation.captured_site_name, "Gupy")

    def test_collect_uses_deterministic_linkedin_collector(self) -> None:
        class FakeLinkedInCollector:
            def __init__(self) -> None:
                self.called = False

            async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
                self.called = True
                return [
                    RawJob(
                        title="Senior Kotlin Engineer",
                        company="ACME",
                        location="Brasil",
                        work_mode="hibrido",
                        salary_text="Nao informado",
                        url="https://www.linkedin.com/jobs/view/123",
                        source_site=site.name,
                        summary="Resumo",
                        description="Descricao",
                    )
                ]

        class FakeAutomation:
            async def run(self, task: str, site: SiteConfig | None = None) -> object:
                raise AssertionError("automation.run nao deveria ser chamado para LinkedIn")

        collector = BrowserUseSiteCollector(
            model_name="model",
            base_url="http://localhost:11434",
            automation=FakeAutomation(),
            linkedin_collector=FakeLinkedInCollector(),
            portal_adapters=(LinkedInCollectorAdapter(), DefaultPortalCollectorAdapter()),
        )

        import asyncio

        jobs = asyncio.run(collector.collect(SiteConfig(name="LinkedIn", search_url="https://example.com"), 5))

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source_site, "LinkedIn")

    def test_selects_linkedin_adapter(self) -> None:
        collector = BrowserUseSiteCollector.__new__(BrowserUseSiteCollector)
        collector.portal_adapters = (
            LinkedInCollectorAdapter(),
            DefaultPortalCollectorAdapter(),
        )

        adapter = collector._adapter_for(SiteConfig(name="LinkedIn", search_url="https://example.com"))

        self.assertIsInstance(adapter, LinkedInCollectorAdapter)

    def test_selects_gupy_adapter(self) -> None:
        collector = BrowserUseSiteCollector.__new__(BrowserUseSiteCollector)
        collector.portal_adapters = (
            GupyCollectorAdapter(),
            DefaultPortalCollectorAdapter(),
        )

        adapter = collector._adapter_for(SiteConfig(name="Gupy", search_url="https://example.com"))

        self.assertIsInstance(adapter, GupyCollectorAdapter)

    def test_selects_indeed_adapter(self) -> None:
        collector = BrowserUseSiteCollector.__new__(BrowserUseSiteCollector)
        collector.portal_adapters = (
            IndeedCollectorAdapter(),
            DefaultPortalCollectorAdapter(),
        )

        adapter = collector._adapter_for(SiteConfig(name="Indeed", search_url="https://example.com"))

        self.assertIsInstance(adapter, IndeedCollectorAdapter)

    def test_falls_back_to_default_adapter(self) -> None:
        collector = BrowserUseSiteCollector.__new__(BrowserUseSiteCollector)
        collector.portal_adapters = (DefaultPortalCollectorAdapter(),)

        adapter = collector._adapter_for(SiteConfig(name="CustomPortal", search_url="https://example.com"))

        self.assertIsInstance(adapter, DefaultPortalCollectorAdapter)
