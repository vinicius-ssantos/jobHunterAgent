import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from job_hunter_agent.core.legacy_matching_config import LegacyMatchingConfig
from job_hunter_agent.core.structured_matching_config import (
    load_structured_matching_source,
    resolve_structured_matching_source,
)


class StructuredMatchingSeniorityTests(TestCase):
    def test_load_structured_matching_source_reads_target_seniorities(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "job_target.json"
            config_path.write_text(
                json.dumps(
                    {
                        "profile": {"summary": "Backend engineer com foco em Java."},
                        "matching": {
                            "include_keywords": ["java"],
                            "minimum_salary_brl": 10000,
                            "minimum_relevance": 6,
                            "target_seniorities": ["senior", "principal"],
                            "allow_unknown_seniority": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_structured_matching_source(config_path)

        self.assertEqual(config.matching.target_seniorities, ("senior", "especialista"))
        self.assertFalse(config.matching.allow_unknown_seniority)

    def test_resolve_structured_matching_source_infers_target_seniority_from_legacy_profile(self) -> None:
        resolved = resolve_structured_matching_source(
            structured_matching_config_path="./missing-job-target.json",
            legacy_matching=LegacyMatchingConfig(
                profile_text="Engenheiro de Software Senior com foco em Java.",
                include_keywords=("java",),
                exclude_keywords=("junior",),
                accepted_work_modes=("remote",),
                minimum_salary_brl=10000,
                minimum_relevance=6,
            ),
            legacy_fallback_enabled=True,
        )

        self.assertEqual(resolved.config.matching.target_seniorities, ("senior",))
        self.assertTrue(resolved.config.matching.allow_unknown_seniority)
