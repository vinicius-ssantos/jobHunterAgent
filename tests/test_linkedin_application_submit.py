import unittest

from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState
from job_hunter_agent.collectors.linkedin_application_submit import (
    evaluate_linkedin_submit_readiness,
)


class LinkedInApplicationSubmitTests(unittest.TestCase):
    def test_evaluate_submit_readiness_accepts_open_modal_with_submit_button(self) -> None:
        decision = evaluate_linkedin_submit_readiness(
            LinkedInApplicationPageState(
                modal_open=True,
                modal_submit_visible=True,
            )
        )

        self.assertTrue(decision.ready)
        self.assertEqual(decision.detail, "")

    def test_evaluate_submit_readiness_describes_blockers_when_submit_not_ready(self) -> None:
        decision = evaluate_linkedin_submit_readiness(
            LinkedInApplicationPageState(
                easy_apply=True,
                modal_open=True,
                modal_next_visible=True,
                modal_sample="next | upload resume",
                cta_text="easy apply",
                modal_headings=("informacoes de contato",),
            ),
            interpretation_detail=" | interpretacao_modal=acao=manual_review",
        )

        self.assertFalse(decision.ready)
        self.assertIn("fluxo nao chegou ao botao de envio", decision.detail)
        self.assertIn("bloqueio=", decision.detail)
        self.assertIn("interpretacao_modal=acao=manual_review", decision.detail)
        self.assertIn("snapshot_modal=", decision.detail)
