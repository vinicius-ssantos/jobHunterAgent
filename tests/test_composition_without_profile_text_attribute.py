from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from job_hunter_agent.application.composition import create_collection_service
from job_hunter_agent.core.domain import SiteConfig
from job_hunter_agent.core.legacy_matching_config import LegacyMatchingConfig


class CompositionWithoutProfileTextAttributeTests(TestCase):
    def test_create_collection_service_does_not_require_profile_text_attribute_when_contract_is_explicit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = SimpleNamespace(
                telegram_token="token",
                telegram_chat_id="chat",
                database_path=root / "jobs.db",
                browser_use_config_dir=root / ".browseruse",
                linkedin_persistent_profile_dir=root / ".browseruse/profiles/linkedin-bootstrap",
                linkedin_storage_state_path=root / ".browseruse/linkedin-storage-state.json",
                candidate_profile_path=root / "candidate_profile.json",
                browser_headless=False,
                linkedin_max_pages_per_cycle=2,
                linkedin_max_page_depth=6,
                linkedin_scroll_stabilization_passes=3,
                relaxed_matching_for_testing=False,
                relaxed_testing_profile_hint="",
                relaxed_testing_remove_exclude_keywords=(),
                relaxed_testing_minimum_relevance=4,
                linkedin_field_repair_enabled=False,
                ollama_model="qwen2.5:7b",
                ollama_url="http://localhost:11434",
                sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
                build_legacy_matching_config=Mock(
                    return_value=LegacyMatchingConfig(
                        profile_text="contract profile",
                        include_keywords=("java",),
                        exclude_keywords=("junior",),
                        accepted_work_modes=("remote",),
                        minimum_salary_brl=10000,
                        minimum_relevance=6,
                    )
                ),
            )
            repository = Mock()
            repository.job_url_exists.return_value = False
            repository.seen_job_url_exists.return_value = False

            with patch(
                "job_hunter_agent.application.composition.build_matching_criteria_from_legacy_config",
                return_value="criteria",
            ) as mocked_build_matching, patch(
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
        settings.build_legacy_matching_config.assert_called_once_with()
        mocked_build_matching.assert_called_once()
