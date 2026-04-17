from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from job_hunter_agent.application.composition import create_collection_service
from job_hunter_agent.core.domain import SiteConfig


class CompositionWithoutProfileTextAttributeTests(TestCase):
    def test_create_collection_service_does_not_require_profile_text_attribute_when_runtime_contract_is_explicit(self) -> None:
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
                structured_matching_config_path=root / "job_target.json",
                structured_matching_fallback_enabled=True,
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
                build_legacy_matching_config=Mock(return_value="legacy"),
            )
            repository = Mock()
            repository.job_url_exists.return_value = False
            repository.seen_job_url_exists.return_value = False

            resolved = SimpleNamespace(
                config="structured",
                used_legacy_fallback=True,
                describe_source=lambda: "fallback legado",
            )

            with patch(
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
        settings.build_legacy_matching_config.assert_called_once_with()
        mocked_build_runtime.assert_called_once_with(
            structured_matching_source="structured",
            relaxed_matching_for_testing=False,
            relaxed_testing_profile_hint="",
            relaxed_testing_remove_exclude_keywords=(),
            relaxed_testing_minimum_relevance=4,
        )
