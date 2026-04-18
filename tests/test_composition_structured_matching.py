import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from job_hunter_agent.application.composition import create_collection_service
from job_hunter_agent.core.domain import SiteConfig
from job_hunter_agent.core.settings import Settings


class CompositionStructuredMatchingTests(TestCase):
    def test_create_collection_service_prefers_structured_matching_file_when_present(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            structured_path = root / "job_target.json"
            structured_path.write_text(
                json.dumps(
                    {
                        "profile": {"summary": "Structured profile"},
                        "matching": {
                            "include_keywords": ["java"],
                            "exclude_keywords": ["junior"],
                            "accepted_work_modes": ["remote"],
                            "minimum_salary_brl": 15000,
                            "minimum_relevance": 8,
                            "allow_unknown_seniority": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            settings = Settings(
                telegram_token="token",
                telegram_chat_id="chat",
                database_path=root / "jobs.db",
                browser_use_config_dir=root / ".browseruse",
                linkedin_persistent_profile_dir=root / ".browseruse/profiles/linkedin-bootstrap",
                linkedin_storage_state_path=root / ".browseruse/linkedin-storage-state.json",
                candidate_profile_path=root / "candidate_profile.json",
                structured_matching_config_path=structured_path,
                sites=(SiteConfig(name="LinkedIn", search_url="https://example.com"),),
            )
            repository = Mock()
            repository.job_url_exists.return_value = False
            repository.seen_job_url_exists.return_value = False

            with patch(
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
        mocked_build_runtime.assert_called_once()
        structured_matching = mocked_build_runtime.call_args.kwargs["structured_matching_source"]
        self.assertEqual(structured_matching.profile.summary, "Structured profile")
        self.assertEqual(structured_matching.matching.minimum_salary_brl, 15000)
        self.assertEqual(structured_matching.matching.minimum_relevance, 8)
