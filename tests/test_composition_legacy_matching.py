from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from job_hunter_agent.application.composition import create_collection_service
from job_hunter_agent.core.domain import SiteConfig
from job_hunter_agent.core.legacy_matching_config import LegacyMatchingConfig
from job_hunter_agent.core.settings import Settings


class CompositionLegacyMatchingTests(TestCase):
    def test_create_collection_service_uses_explicit_legacy_matching_contract(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                database_path=root / "jobs.db",
                browser_use_config_dir=root / ".browseruse",
                linkedin_persistent_profile_dir=root / ".browseruse/profiles/linkedin-bootstrap",
                linkedin_storage_state_path=root / ".browseruse/linkedin-storage-state.json",
                candidate_profile_path=root / "candidate_profile.json",
                structured_matching_fallback_enabled=True,
                sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
            )
            repository = Mock()
            repository.job_url_exists.return_value = False
            repository.seen_job_url_exists.return_value = False

            legacy = LegacyMatchingConfig(
                profile_text="LEGACY PROFILE CONTRACT",
                include_keywords=("java",),
                exclude_keywords=("junior",),
                accepted_work_modes=("remote",),
                minimum_salary_brl=12345,
                minimum_relevance=7,
            )

            resolved = Mock(
                config="resolved_matching",
                used_legacy_fallback=True,
                describe_source=Mock(return_value="fallback legado"),
            )

            with patch.object(Settings, "build_legacy_matching_config", return_value=legacy) as mocked_build_legacy, patch(
                "job_hunter_agent.application.composition.resolve_structured_matching_source",
                return_value=resolved,
            ), patch(
                "job_hunter_agent.application.composition.build_runtime_matching_profile_from_structured_source",
                return_value="runtime_profile",
            ) as mocked_build_runtime, patch(
                "job_hunter_agent.application.composition.LinkedInDeterministicCollector",
                return_value="linkedin_collector",
            ), patch(
                "job_hunter_agent.application.composition.BrowserUseSiteCollector",
                return_value="site_collector",
            ), patch(
                "job_hunter_agent.application.composition.HybridJobScorer",
                return_value="scorer",
            ):
                service = create_collection_service(settings, repository)

        self.assertIsNotNone(service)
        mocked_build_legacy.assert_called_once_with()
        mocked_build_runtime.assert_called_once_with(
            structured_matching_source="resolved_matching",
            relaxed_matching_for_testing=settings.relaxed_matching_for_testing,
            relaxed_testing_profile_hint=settings.relaxed_testing_profile_hint,
            relaxed_testing_remove_exclude_keywords=settings.relaxed_testing_remove_exclude_keywords,
            relaxed_testing_minimum_relevance=settings.relaxed_testing_minimum_relevance,
        )
