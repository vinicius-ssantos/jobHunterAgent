import shutil
import sqlite3
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase

from job_hunter_agent.collector import (
    automation_result_to_text,
    BrowserUseSiteCollector,
    build_available_file_paths,
    clean_linkedin_company,
    clean_linkedin_description,
    clean_linkedin_location,
    clean_linkedin_summary,
    clean_linkedin_title,
    DefaultPortalCollectorAdapter,
    GupyCollectorAdapter,
    IndeedCollectorAdapter,
    JobCollectionService,
    LinkedInCollectorAdapter,
    build_external_key,
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
from job_hunter_agent.domain import JobPosting, RawJob, ScoredJob, SiteConfig
from job_hunter_agent.linkedin import LinkedInDeterministicCollector
from job_hunter_agent.repository import SqliteJobRepository
from job_hunter_agent.settings import Settings
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
    def score(self, raw_job: RawJob, settings: Settings) -> ScoredJob:
        if "PHP" in raw_job.title:
            return ScoredJob(relevance=2, rationale="Tecnologia excluida.", accepted=False)
        return ScoredJob(relevance=8, rationale="Bom fit tecnico.", accepted=True)


class FlakyScorer:
    def score(self, raw_job: RawJob, settings: Settings) -> ScoredJob:
        if "Kotlin" in raw_job.title:
            raise RuntimeError("modelo indisponivel")
        return ScoredJob(relevance=7, rationale="Fallback valido.", accepted=True)


class FailingIfCalledScorer:
    def score(self, raw_job: RawJob, settings: Settings) -> ScoredJob:
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
            sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
        )

    async def asyncTearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_collect_new_jobs_filters_and_saves_only_relevant_jobs(self) -> None:
        service = JobCollectionService(
            settings=self.settings,
            repository=self.repository,
            site_collector=FakeSiteCollector(),
            scorer=FakeScorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Kotlin Engineer")
        self.assertTrue(self.repository.job_exists(jobs[0].url, jobs[0].external_key))

    async def test_collect_new_jobs_filters_out_wrong_work_mode_before_scoring(self) -> None:
        service = JobCollectionService(
            settings=Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                accepted_work_modes=("remoto",),
                sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
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
            repository=self.repository,
            site_collector=InvalidFakeSiteCollector(),
            scorer=FakeScorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(jobs, [])

    async def test_collect_new_jobs_report_tracks_portal_failures(self) -> None:
        service = JobCollectionService(
            settings=self.settings,
            repository=self.repository,
            site_collector=FailingSiteCollector(),
            scorer=FakeScorer(),
        )

        report = await service.collect_new_jobs_report()

        self.assertEqual(report.jobs_seen, 0)
        self.assertEqual(report.jobs_saved, 0)
        self.assertEqual(report.errors, 1)

    async def test_collect_new_jobs_report_times_out_slow_portal(self) -> None:
        service = JobCollectionService(
            settings=Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                portal_collection_timeout_seconds=0,
                sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
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
        self.assertIn("duplicadas=1", last_log[0])

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
            repository=self.repository,
            site_collector=FakeSiteCollector(),
            scorer=FailingIfCalledScorer(),
        )

        jobs = await service.collect_new_jobs()

        self.assertEqual(jobs, [])


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

    def test_strip_title_prefix_from_location_removes_contaminated_title(self) -> None:
        self.assertEqual(
            strip_title_prefix_from_location(
                "Desenvolvedor Java São Paulo, São Paulo, Brasil", "Desenvolvedor Java"
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
