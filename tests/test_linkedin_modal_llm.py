import unittest

from job_hunter_agent.linkedin_application import LinkedInApplicationPageState
from job_hunter_agent.linkedin_modal_llm import (
    build_linkedin_modal_snapshot_payload,
    deterministic_interpret_linkedin_modal,
    format_linkedin_modal_interpretation,
    parse_linkedin_modal_interpretation_response,
)


class LinkedInModalInterpreterTests(unittest.TestCase):
    def test_build_snapshot_payload_contains_modal_parts(self) -> None:
        payload = build_linkedin_modal_snapshot_payload(
            LinkedInApplicationPageState(
                modal_open=True,
                modal_headings=("informacoes de contato",),
                modal_buttons=("next", "review"),
                modal_fields=("email", "phone"),
                resumable_fields=("telefone",),
                filled_fields=("telefone",),
                modal_next_visible=True,
            )
        )

        self.assertTrue(payload["modal_open"])
        self.assertEqual(payload["headings"], ["informacoes de contato"])
        self.assertEqual(payload["buttons"], ["next", "review"])
        self.assertEqual(payload["fields"], ["email", "phone"])

    def test_deterministic_interpreter_detects_review_final(self) -> None:
        interpretation = deterministic_interpret_linkedin_modal(
            LinkedInApplicationPageState(
                modal_open=True,
                modal_submit_visible=True,
                ready_to_submit=True,
            )
        )

        self.assertEqual(interpretation.step_type, "review_final")
        self.assertEqual(interpretation.recommended_action, "submit_if_authorized")

    def test_deterministic_interpreter_detects_resume_upload(self) -> None:
        interpretation = deterministic_interpret_linkedin_modal(
            LinkedInApplicationPageState(
                modal_open=True,
                modal_file_upload=True,
                uploaded_resume=False,
            )
        )

        self.assertEqual(interpretation.step_type, "resume_upload")
        self.assertEqual(interpretation.recommended_action, "upload_resume")

    def test_parse_linkedin_modal_interpretation_response_accepts_valid_json(self) -> None:
        interpretation = parse_linkedin_modal_interpretation_response(
            '{"step_type":"multi_step_form","recommended_action":"click_next","confidence":0.82,"rationale":"ha etapas intermediarias"}'
        )

        self.assertEqual(interpretation.step_type, "multi_step_form")
        self.assertEqual(interpretation.recommended_action, "click_next")
        self.assertAlmostEqual(interpretation.confidence, 0.82)

    def test_parse_linkedin_modal_interpretation_response_rejects_invalid_values(self) -> None:
        interpretation = parse_linkedin_modal_interpretation_response(
            '{"step_type":"whatever","recommended_action":"do_anything","confidence":1,"rationale":"x"}'
        )

        self.assertEqual(interpretation.step_type, "unknown")
        self.assertEqual(interpretation.recommended_action, "manual_review")

    def test_format_linkedin_modal_interpretation_is_compact(self) -> None:
        formatted = format_linkedin_modal_interpretation(
            parse_linkedin_modal_interpretation_response(
                '{"step_type":"contact","recommended_action":"fill_contact","confidence":0.71,"rationale":"campos de contato visiveis"}'
            )
        )

        self.assertIn("interpretacao_modal=", formatted)
        self.assertIn("etapa=contact", formatted)
        self.assertIn("acao=fill_contact", formatted)

