import unittest

from job_hunter_agent.linkedin_application import (
    LinkedInApplicationPageState,
    classify_linkedin_application_page_state,
)


class LinkedInApplicationInspectorTests(unittest.TestCase):
    def test_classify_page_state_marks_single_step_easy_apply_as_ready(self) -> None:
        inspection = classify_linkedin_application_page_state(
            LinkedInApplicationPageState(
                easy_apply=True,
                modal_open=True,
                modal_submit_visible=True,
                resumable_fields=("email", "telefone"),
                cta_text="easy apply",
                modal_sample="submit application | phone number",
            )
        )

        self.assertEqual(inspection.outcome, "ready")
        self.assertIn("fluxo simplificado", inspection.detail)
        self.assertIn("cta=easy apply", inspection.detail)
        self.assertIn("campos=email, telefone", inspection.detail)

    def test_classify_page_state_marks_multistep_easy_apply_as_manual_review(self) -> None:
        inspection = classify_linkedin_application_page_state(
            LinkedInApplicationPageState(
                easy_apply=True,
                modal_open=True,
                modal_next_visible=True,
                modal_file_upload=True,
                resumable_fields=("email", "telefone", "codigo_pais"),
                filled_fields=("telefone",),
                progressed_to_next_step=True,
                cta_text="candidatura simplificada",
                modal_sample="next | upload resume",
            )
        )

        self.assertEqual(inspection.outcome, "manual_review")
        self.assertIn("preenchidos=telefone", inspection.detail)
        self.assertIn("avancou_proxima_etapa=sim", inspection.detail)
        self.assertIn("passos_adicionais=sim", inspection.detail)
        self.assertIn("upload_cv=sim", inspection.detail)
        self.assertIn("campos=email, telefone, codigo_pais", inspection.detail)

    def test_classify_page_state_blocks_external_apply(self) -> None:
        inspection = classify_linkedin_application_page_state(
            LinkedInApplicationPageState(external_apply=True)
        )

        self.assertEqual(inspection.outcome, "blocked")
        self.assertIn("candidatura externa", inspection.detail)

    def test_classify_page_state_marks_unopened_easy_apply_as_manual_review(self) -> None:
        inspection = classify_linkedin_application_page_state(
            LinkedInApplicationPageState(easy_apply=True, cta_text="easy apply")
        )

        self.assertEqual(inspection.outcome, "manual_review")
        self.assertIn("modal nao abriu", inspection.detail)
