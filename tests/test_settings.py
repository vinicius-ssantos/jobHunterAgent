from unittest import TestCase
from pathlib import Path

from job_hunter_agent.core.runtime_matching import RuntimeMatchingPolicy, RuntimeMatchingProfile, build_runtime_matching_profile_from_structured_source
from job_hunter_agent.core.settings import Settings, load_settings
from job_hunter_agent.core.structured_matching_config import StructuredCandidateProfile, StructuredMatchingConfig, StructuredMatchingSource


class SettingsTests(TestCase):
    def test_settings_accepts_placeholder_telegram_credentials_for_non_telegram_execution(self) -> None:
        previous_env_file = Settings.model_config.get("env_file")
        Settings.model_config["env_file"] = None
        try:
            settings = Settings()
        finally:
            Settings.model_config["env_file"] = previous_env_file

        self.assertEqual(settings.telegram_token, "SEU_TOKEN_AQUI")
        self.assertEqual(settings.telegram_chat_id, "SEU_CHAT_ID_AQUI")

    def test_load_settings_reads_environment_overrides(self) -> None:
        previous_env_file = Settings.model_config.get("env_file")
        Settings.model_config["env_file"] = None
        try:
            settings = Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                profile_text="Backend engineer",
                collection_time="09:30",
                save_failure_artifacts=False,
            )
        finally:
            Settings.model_config["env_file"] = previous_env_file

        self.assertEqual(settings.telegram_token, "token")
        self.assertEqual(settings.telegram_chat_id, "chat")
        self.assertEqual(settings.profile_text, "Backend engineer")
        self.assertEqual(settings.collection_time, "09:30")
        self.assertEqual(settings.review_polling_grace_seconds, 120)
        self.assertEqual(settings.linkedin_max_pages_per_cycle, 2)
        self.assertEqual(settings.linkedin_max_page_depth, 6)
        self.assertEqual(settings.linkedin_scroll_stabilization_passes, 3)
        self.assertFalse(settings.save_failure_artifacts)
        self.assertEqual(settings.application_contact_email, "")
        self.assertEqual(settings.application_phone, "")
        self.assertEqual(settings.application_phone_country_code, "")
        self.assertEqual(str(settings.candidate_profile_path), "candidate_profile.json")
        self.assertFalse(settings.relaxed_matching_for_testing)
        self.assertFalse(settings.structured_matching_fallback_enabled)
        self.assertTrue(settings.linkedin_field_repair_enabled)
        self.assertTrue(settings.application_priority_llm_enabled)
        self.assertEqual(settings.failure_artifacts_dir, Path("./.artifacts/linkedin_failures"))
        self.assertEqual(settings.sites[0].search_url, "https://www.linkedin.com/jobs/search/")

    def test_load_settings_from_env_prefix(self) -> None:
        previous_prefix = Settings.model_config.get("env_prefix")
        previous_env_file = Settings.model_config.get("env_file")
        Settings.model_config["env_prefix"] = "JOB_HUNTER_"
        Settings.model_config["env_file"] = None
        try:
            import os
            from unittest.mock import patch

            with patch.dict(
                os.environ,
                {
                    "JOB_HUNTER_TELEGRAM_TOKEN": "token",
                    "JOB_HUNTER_TELEGRAM_CHAT_ID": "chat",
                    "JOB_HUNTER_PROFILE_TEXT": "Backend engineer",
                    "JOB_HUNTER_COLLECTION_TIME": "09:30",
                },
                clear=False,
            ):
                settings = load_settings()
        finally:
            Settings.model_config["env_prefix"] = previous_prefix
            Settings.model_config["env_file"] = previous_env_file

        self.assertEqual(settings.telegram_token, "token")
        self.assertEqual(settings.telegram_chat_id, "chat")

    def test_load_settings_accepts_application_contact_overrides(self) -> None:
        settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            application_contact_email="vinicius@example.com",
            application_phone="11999999999",
            application_phone_country_code="Brazil (+55)",
        )

        self.assertEqual(settings.application_contact_email, "vinicius@example.com")
        self.assertEqual(settings.application_phone, "11999999999")
        self.assertEqual(settings.application_phone_country_code, "Brazil (+55)")

    def test_rejects_invalid_application_contact_email(self) -> None:
        with self.assertRaisesRegex(ValueError, "JOB_HUNTER_APPLICATION_CONTACT_EMAIL"):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                application_contact_email="vinicius-at-example.com",
            )

    def test_rejects_invalid_application_phone(self) -> None:
        with self.assertRaisesRegex(ValueError, "JOB_HUNTER_APPLICATION_PHONE"):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                application_phone="1234",
            )

    def test_rejects_invalid_application_phone_country_code(self) -> None:
        with self.assertRaisesRegex(ValueError, "JOB_HUNTER_APPLICATION_PHONE_COUNTRY_CODE"):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                application_phone_country_code="Brasil",
            )

    def test_rejects_directory_as_resume_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "resume_path deve apontar para um arquivo"):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                resume_path=Path("."),
            )

    def test_rejects_invalid_collection_time(self) -> None:
        with self.assertRaises(ValueError):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                collection_time="99:99",
            )

    def test_settings_accepts_empty_telegram_values_for_non_telegram_execution(self) -> None:
        settings = Settings(
            telegram_token="",
            telegram_chat_id="",
        )

        self.assertEqual(settings.telegram_token, "")
        self.assertEqual(settings.telegram_chat_id, "")

    def test_rejects_without_active_sites(self) -> None:
        from job_hunter_agent.core.domain import SiteConfig

        with self.assertRaises(ValueError):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                sites=(SiteConfig(name="LinkedIn", search_url="https://example.com", enabled=False),),
            )

    def test_relaxed_matching_for_testing_changes_scoring_inputs(self) -> None:
        settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            relaxed_matching_for_testing=True,
        )
        source = StructuredMatchingSource(
            profile=StructuredCandidateProfile(summary=settings.profile_text),
            matching=StructuredMatchingConfig(
                include_keywords=settings.include_keywords,
                exclude_keywords=settings.exclude_keywords,
                accepted_work_modes=settings.accepted_work_modes,
                minimum_salary_brl=settings.minimum_salary_brl,
                minimum_relevance=settings.minimum_relevance,
            ),
        )

        profile = build_runtime_matching_profile_from_structured_source(
            structured_matching_source=source,
            relaxed_matching_for_testing=settings.relaxed_matching_for_testing,
            relaxed_testing_profile_hint=settings.relaxed_testing_profile_hint,
            relaxed_testing_remove_exclude_keywords=settings.relaxed_testing_remove_exclude_keywords,
            relaxed_testing_minimum_relevance=settings.relaxed_testing_minimum_relevance,
        )

        self.assertNotIn("junior", profile.exclude_keywords)
        self.assertIn("junior e pleno", profile.candidate_summary)
        self.assertEqual(profile.minimum_relevance, 4)

    def test_runtime_matching_profile_exposes_validated_business_inputs(self) -> None:
        profile = RuntimeMatchingProfile(
            candidate_summary="Backend engineer",
            include_keywords=("java", "kotlin"),
            exclude_keywords=("junior", "php"),
            accepted_work_modes=("remoto", "hibrido"),
            minimum_salary_brl=12000,
            minimum_relevance=7,
        )

        self.assertEqual(profile.candidate_summary, "Backend engineer")
        self.assertEqual(profile.include_keywords, ("java", "kotlin"))
        self.assertEqual(profile.exclude_keywords, ("junior", "php"))
        self.assertEqual(profile.accepted_work_modes, ("remoto", "hibrido"))
        self.assertEqual(profile.minimum_salary_brl, 12000)
        self.assertEqual(profile.minimum_relevance, 7)

    def test_runtime_matching_policy_centralizes_exclusion_work_mode_salary_and_relevance(self) -> None:
        policy = RuntimeMatchingPolicy(
            RuntimeMatchingProfile(
                candidate_summary="Backend engineer",
                include_keywords=("java",),
                exclude_keywords=("junior", "php"),
                accepted_work_modes=("remoto", "hibrido"),
                minimum_salary_brl=10000,
                minimum_relevance=6,
            )
        )

        self.assertTrue(policy.contains_excluded_keywords("vaga junior com php"))
        self.assertTrue(policy.accepts_work_mode("Remoto"))
        self.assertFalse(policy.accepts_work_mode("Presencial"))
        self.assertTrue(policy.accepts_salary_floor(12000))
        self.assertFalse(policy.accepts_salary_floor(8000))
        self.assertTrue(policy.accepts_relevance(7))
        self.assertFalse(policy.accepts_relevance(5))

    def test_relaxed_matching_for_testing_can_be_tuned_by_settings(self) -> None:
        settings = Settings(
            telegram_token="token",
            telegram_chat_id="chat",
            relaxed_matching_for_testing=True,
            relaxed_testing_profile_hint="Aceite tambem vagas pleno e mid-level.",
            relaxed_testing_remove_exclude_keywords=("junior", "trainee"),
            relaxed_testing_minimum_relevance=5,
        )
        source = StructuredMatchingSource(
            profile=StructuredCandidateProfile(summary=settings.profile_text),
            matching=StructuredMatchingConfig(
                include_keywords=settings.include_keywords,
                exclude_keywords=settings.exclude_keywords,
                accepted_work_modes=settings.accepted_work_modes,
                minimum_salary_brl=settings.minimum_salary_brl,
                minimum_relevance=settings.minimum_relevance,
            ),
        )

        profile = build_runtime_matching_profile_from_structured_source(
            structured_matching_source=source,
            relaxed_matching_for_testing=settings.relaxed_matching_for_testing,
            relaxed_testing_profile_hint=settings.relaxed_testing_profile_hint,
            relaxed_testing_remove_exclude_keywords=settings.relaxed_testing_remove_exclude_keywords,
            relaxed_testing_minimum_relevance=settings.relaxed_testing_minimum_relevance,
        )

        self.assertIn("pleno e mid-level", profile.candidate_summary)
        self.assertNotIn("junior", profile.exclude_keywords)
        self.assertNotIn("trainee", profile.exclude_keywords)
        self.assertEqual(profile.minimum_relevance, 5)

    def test_rejects_invalid_linkedin_max_pages_per_cycle(self) -> None:
        with self.assertRaises(ValueError):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                linkedin_max_pages_per_cycle=0,
            )

    def test_rejects_invalid_linkedin_max_page_depth(self) -> None:
        with self.assertRaises(ValueError):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                linkedin_max_page_depth=0,
            )

    def test_rejects_invalid_linkedin_scroll_stabilization_passes(self) -> None:
        with self.assertRaises(ValueError):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                linkedin_scroll_stabilization_passes=0,
            )

    def test_rejects_invalid_priority_high_min_relevance(self) -> None:
        with self.assertRaisesRegex(ValueError, "JOB_HUNTER_PRIORITY_HIGH_MIN_RELEVANCE"):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                priority_high_min_relevance=11,
            )

    def test_rejects_priority_medium_above_high(self) -> None:
        with self.assertRaisesRegex(ValueError, "JOB_HUNTER_PRIORITY_MEDIUM_MIN_RELEVANCE"):
            Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                priority_high_min_relevance=7,
                priority_medium_min_relevance=8,
            )
