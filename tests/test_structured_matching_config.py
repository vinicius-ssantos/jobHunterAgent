import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from job_hunter_agent.core.legacy_matching_config import LegacyMatchingConfig
from job_hunter_agent.core.structured_matching_config import (
    LinkedInPrecisionGateConfig,
    StructuredMatchingSource,
    load_structured_matching_source,
    resolve_structured_matching_source,
)


class StructuredMatchingConfigTests(TestCase):
    def test_load_structured_matching_source_reads_valid_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "job_target.json"
            config_path.write_text(
                json.dumps(
                    {
                        "profile": {"summary": "Backend engineer com foco em Java."},
                        "matching": {
                            "include_keywords": ["java", "kotlin"],
                            "exclude_keywords": ["junior"],
                            "accepted_work_modes": ["remote"],
                            "minimum_salary_brl": 10000,
                            "minimum_relevance": 6,
                            "allow_unknown_seniority": False,
                            "linkedin_precision_gate": {
                                "required_terms": ["java"],
                                "any_terms": ["backend", "spring"],
                                "blocked_terms": ["sales"],
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_structured_matching_source(config_path)

        self.assertIsInstance(config, StructuredMatchingSource)
        self.assertEqual(config.profile.summary, "Backend engineer com foco em Java.")
        self.assertEqual(config.matching.include_keywords, ("java", "kotlin"))
        self.assertEqual(config.matching.exclude_keywords, ("junior",))
        self.assertEqual(config.matching.accepted_work_modes, ("remote",))
        self.assertEqual(config.matching.minimum_salary_brl, 10000)
        self.assertEqual(config.matching.minimum_relevance, 6)
        self.assertFalse(config.matching.allow_unknown_seniority)
        self.assertEqual(
            config.matching.linkedin_precision_gate,
            LinkedInPrecisionGateConfig(
                required_terms=("java",),
                any_terms=("backend", "spring"),
                blocked_terms=("sales",),
            ),
        )

    def test_load_structured_matching_source_defaults_linkedin_precision_gate_to_include_keywords(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "job_target.json"
            config_path.write_text(
                json.dumps(
                    {
                        "profile": {"summary": "Backend engineer com foco em Java."},
                        "matching": {
                            "include_keywords": ["java", "kotlin"],
                            "minimum_salary_brl": 0,
                            "minimum_relevance": 6,
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_structured_matching_source(config_path)

        self.assertEqual(config.matching.linkedin_precision_gate.required_terms, ())
        self.assertEqual(config.matching.linkedin_precision_gate.any_terms, ("java", "kotlin"))
        self.assertEqual(config.matching.linkedin_precision_gate.blocked_terms, ())

    def test_resolve_structured_matching_source_falls_back_to_legacy_when_file_is_missing(self) -> None:
        legacy = LegacyMatchingConfig(
            profile_text="Legacy profile",
            include_keywords=("java",),
            exclude_keywords=("junior",),
            accepted_work_modes=("remote",),
            minimum_salary_brl=9000,
            minimum_relevance=5,
        )

        resolved = resolve_structured_matching_source(
            structured_matching_config_path="./missing-job-target.json",
            legacy_matching=legacy,
            legacy_fallback_enabled=True,
        )

        self.assertTrue(resolved.used_legacy_fallback)
        self.assertEqual(resolved.config.profile.summary, "Legacy profile")
        self.assertEqual(resolved.config.matching.include_keywords, ("java",))
        self.assertEqual(resolved.config.matching.linkedin_precision_gate.any_terms, ("java",))

    def test_resolve_structured_matching_source_fails_fast_when_fallback_is_disabled(self) -> None:
        legacy = LegacyMatchingConfig(
            profile_text="Legacy profile",
            include_keywords=("java",),
            exclude_keywords=("junior",),
            accepted_work_modes=("remote",),
            minimum_salary_brl=9000,
            minimum_relevance=5,
        )

        with self.assertRaises(ValueError):
            resolve_structured_matching_source(
                structured_matching_config_path="./missing-job-target.json",
                legacy_matching=legacy,
                legacy_fallback_enabled=False,
            )
