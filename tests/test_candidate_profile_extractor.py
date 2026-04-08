from pathlib import Path
from unittest import TestCase

from job_hunter_agent.llm.candidate_profile_extractor import (
    CandidateProfileSuggestion,
    merge_candidate_profile_suggestions,
    parse_candidate_profile_suggestion_response,
)
from tests.tmp_workspace import prepare_workspace_tmp_dir


class CandidateProfileExtractorTests(TestCase):
    def test_parse_candidate_profile_suggestion_response_normalizes_supported_skills(self) -> None:
        suggestion = parse_candidate_profile_suggestion_response(
            """
            {
              "experience_years": {
                "Java": {"suggested": 8},
                "Angular Framework": {"suggested": 4},
                "EJB": {"suggested": 2}
              },
              "rationale": "extraido do curriculo"
            }
            """
        )

        self.assertEqual(suggestion.experience_years["java"], 8)
        self.assertEqual(suggestion.experience_years["angular"], 4)
        self.assertEqual(suggestion.experience_years["ejb"], 2)

    def test_merge_candidate_profile_suggestions_preserves_confirmed_values(self) -> None:
        tmp_dir = prepare_workspace_tmp_dir("candidate-profile-suggestions")
        output_path = Path(tmp_dir) / "candidate_profile.json"
        output_path.write_text(
            """
            {
              "experience_years": {
                "java": {"suggested": 6, "confirmed": 8}
              }
            }
            """,
            encoding="utf-8",
        )

        merge_candidate_profile_suggestions(
            output_path=output_path,
            suggestion=CandidateProfileSuggestion(experience_years={"java": 7, "angular": 4}),
            source_resume="curriculo.pdf",
        )

        written = output_path.read_text(encoding="utf-8")
        self.assertIn('"confirmed": 8', written)
        self.assertIn('"angular"', written)
