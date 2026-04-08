from pathlib import Path
from unittest import TestCase

from job_hunter_agent.core.candidate_profile import (
    CandidateProfile,
    extract_skill_key_from_experience_question,
    extract_supported_experience_answers,
    load_candidate_profile,
)
from tests.tmp_workspace import prepare_workspace_tmp_dir


class CandidateProfileTests(TestCase):
    def test_load_candidate_profile_uses_only_confirmed_years(self) -> None:
        tmp_dir = prepare_workspace_tmp_dir("candidate-profile")
        path = Path(tmp_dir) / "candidate_profile.json"
        path.write_text(
            """
            {
              "experience_years": {
                "java": {"suggested": 7, "confirmed": 8},
                "angular": {"suggested": 4},
                "ejb": 2
              }
            }
            """,
            encoding="utf-8",
        )

        profile = load_candidate_profile(path)

        self.assertEqual(profile.years_for_skill("java"), 8)
        self.assertEqual(profile.years_for_skill("ejb"), 2)
        self.assertIsNone(profile.years_for_skill("angular"))

    def test_extract_skill_key_from_experience_question_maps_supported_stack(self) -> None:
        self.assertEqual(
            extract_skill_key_from_experience_question("Há quantos anos você já usa Angular (framework) no trabalho?"),
            "angular",
        )
        self.assertEqual(
            extract_skill_key_from_experience_question("How many years of experience do you have with Java?"),
            "java",
        )

    def test_extract_supported_experience_answers_reports_unresolved_questions(self) -> None:
        profile = CandidateProfile(confirmed_experience_years={"java": 8, "angular": 4})

        answers, unresolved = extract_supported_experience_answers(
            (
                "Há quantos anos você já usa Java no trabalho?",
                "Há quantos anos você já usa EJB no trabalho?",
            ),
            profile,
        )

        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0].skill_key, "java")
        self.assertEqual(answers[0].years, 8)
        self.assertEqual(unresolved, ("Há quantos anos você já usa EJB no trabalho?",))
