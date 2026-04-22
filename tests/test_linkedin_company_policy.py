import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from job_hunter_agent.core.linkedin_company_policy import (
    get_runtime_linkedin_company_policy,
    load_linkedin_company_policy,
    set_runtime_linkedin_company_policy_path,
)


class LinkedInCompanyPolicyTests(TestCase):
    def setUp(self) -> None:
        self._original_runtime_path = Path("./linkedin_company_policy.json")
        set_runtime_linkedin_company_policy_path(self._original_runtime_path)

    def tearDown(self) -> None:
        set_runtime_linkedin_company_policy_path(self._original_runtime_path)

    def test_load_linkedin_company_policy_reads_valid_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "company_policy.json"
            path.write_text(
                json.dumps(
                    {
                        "trailing_location_fragments": ["osasco"],
                        "standalone_location_tokens": ["osasco", "brasil"],
                        "noise_phrases": ["promovida"],
                        "work_mode_tokens": ["remoto"],
                    }
                ),
                encoding="utf-8",
            )
            policy = load_linkedin_company_policy(path)

        self.assertEqual(policy.trailing_location_fragments, ("osasco",))
        self.assertIn("brasil", policy.standalone_location_set)
        self.assertIn("promovida", policy.noise_phrases)
        self.assertIn("remoto", policy.work_mode_set)

    def test_get_runtime_linkedin_company_policy_uses_runtime_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "company_policy.json"
            path.write_text(
                json.dumps(
                    {
                        "trailing_location_fragments": ["curitiba"],
                        "standalone_location_tokens": ["curitiba"],
                        "noise_phrases": ["visualizado"],
                        "work_mode_tokens": ["hybrid"],
                    }
                ),
                encoding="utf-8",
            )
            set_runtime_linkedin_company_policy_path(path)
            policy = get_runtime_linkedin_company_policy()

        self.assertEqual(policy.trailing_location_fragments, ("curitiba",))
        self.assertIn("hybrid", policy.work_mode_set)
