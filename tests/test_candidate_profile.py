from pathlib import Path
from unittest import TestCase

from job_hunter_agent.core.candidate_profile import (
    build_question_key,
    CandidateProfile,
    extract_skill_key_from_experience_question,
    extract_supported_experience_answers,
    load_candidate_profile,
    record_pending_questions,
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

    def test_load_candidate_profile_uses_confirmed_question_entries_for_supported_skills(self) -> None:
        tmp_dir = prepare_workspace_tmp_dir("candidate-profile-questions")
        path = Path(tmp_dir) / "candidate_profile.json"
        path.write_text(
            """
            {
              "experience_years": {
                "java": {"suggested": 7, "confirmed": 8}
              },
              "questions": {
                "angular_question": {
                  "question": "Há quantos anos você já usa Angular (framework) no trabalho?",
                  "type": "experience_years",
                  "skill": "angular",
                  "confirmed": 4
                },
                "ejb_question": {
                  "question": "Há quantos anos você já usa EJB no trabalho?",
                  "type": "experience_years",
                  "skill": "ejb",
                  "confirmed": 1
                }
              }
            }
            """,
            encoding="utf-8",
        )

        profile = load_candidate_profile(path)

        self.assertEqual(profile.years_for_skill("java"), 8)
        self.assertEqual(profile.years_for_skill("angular"), 4)
        self.assertEqual(profile.years_for_skill("ejb"), 1)

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

    def test_record_pending_questions_persists_unconfirmed_question_entries(self) -> None:
        tmp_dir = prepare_workspace_tmp_dir("candidate-profile-pending")
        path = Path(tmp_dir) / "candidate_profile.json"

        record_pending_questions(
            path,
            (
                "Há quantos anos você já usa Java no trabalho?",
                "Você precisa de visto para trabalhar no Brasil?",
            ),
        )

        written = path.read_text(encoding="utf-8")
        self.assertIn(build_question_key("Há quantos anos você já usa Java no trabalho?"), written)
        self.assertIn('"type": "experience_years"', written)
        self.assertIn('"skill": "java"', written)
        self.assertIn('"confirmed": null', written)
        self.assertIn('"type": "unknown"', written)
