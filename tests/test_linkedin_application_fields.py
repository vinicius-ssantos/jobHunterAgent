from pathlib import Path
import unittest

from job_hunter_agent.collectors.linkedin_application_fields import LinkedInEasyApplyFieldFiller
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState
from job_hunter_agent.core.candidate_profile import CandidateProfile
from tests.tmp_workspace import prepare_workspace_tmp_dir


class LinkedInApplicationFieldsTests(unittest.TestCase):
    def test_try_fill_safe_fields_returns_filled_field_names(self) -> None:
        class _Locator:
            async def count(self):
                return 1

        class _Page:
            def locator(self, selector):
                return _Locator()

            async def evaluate(self, script, payload):
                return ["email", "telefone", "codigo_pais"]

        filler = LinkedInEasyApplyFieldFiller(
            contact_email="vinicius@example.com",
            phone="11999999999",
            phone_country_code="+55",
        )

        import asyncio

        filled = asyncio.run(filler.try_fill_safe_fields(_Page()))

        self.assertEqual(filled, ("email", "telefone", "codigo_pais"))

    def test_try_fill_supported_profile_answers_returns_answered_and_unresolved(self) -> None:
        class _Page:
            async def evaluate(self, script, answers):
                return ["ha quantos anos voce usa java?"]

        filler = LinkedInEasyApplyFieldFiller(
            contact_email="",
            phone="",
            phone_country_code="",
            candidate_profile=CandidateProfile(confirmed_experience_years={"java": 5}),
        )

        import asyncio

        answered, unresolved = asyncio.run(
            filler.try_fill_supported_profile_answers(
                _Page(),
                LinkedInApplicationPageState(
                    modal_questions=(
                        "ha quantos anos voce usa java?",
                        "ha quantos anos voce usa cobol?",
                    )
                ),
            )
        )

        self.assertEqual(answered, ("ha quantos anos voce usa java?",))
        self.assertIn("ha quantos anos voce usa cobol?", unresolved)

    def test_record_pending_questions_persists_when_profile_path_exists(self) -> None:
        tmp = Path(prepare_workspace_tmp_dir("linkedin-fields-profile"))
        profile_path = tmp / "candidate_profile.json"
        profile_path.write_text('{"name":"Vinicius"}', encoding="utf-8")

        filler = LinkedInEasyApplyFieldFiller(
            contact_email="",
            phone="",
            phone_country_code="",
            candidate_profile_path=profile_path,
        )

        filler.record_pending_questions(("pergunta x",))

        content = profile_path.read_text(encoding="utf-8")
        self.assertIn("pergunta x", content)
