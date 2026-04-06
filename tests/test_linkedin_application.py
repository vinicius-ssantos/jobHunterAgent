import unittest
from pathlib import Path

from job_hunter_agent.linkedin_application import (
    build_linkedin_modal_snapshot,
    describe_linkedin_easy_apply_entrypoint,
    LinkedInApplicationPageState,
    classify_linkedin_application_page_state,
    describe_linkedin_modal_blocker,
    LinkedInApplicationFlowInspector,
)
from tests.tmp_workspace import prepare_workspace_tmp_dir


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
        self.assertIn("pronto para submissao assistida", inspection.detail)
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
                uploaded_resume=True,
                cta_text="candidatura simplificada",
                modal_sample="next | upload resume",
            )
        )

        self.assertEqual(inspection.outcome, "manual_review")
        self.assertIn("preenchidos=telefone", inspection.detail)
        self.assertIn("avancou_proxima_etapa=sim", inspection.detail)
        self.assertIn("curriculo_carregado=sim", inspection.detail)
        self.assertIn("passos_adicionais=sim", inspection.detail)
        self.assertIn("upload_cv=sim", inspection.detail)
        self.assertIn("campos=email, telefone, codigo_pais", inspection.detail)

    def test_classify_page_state_marks_review_ready_flow_as_ready(self) -> None:
        inspection = classify_linkedin_application_page_state(
            LinkedInApplicationPageState(
                easy_apply=True,
                modal_open=True,
                modal_submit_visible=True,
                filled_fields=("telefone",),
                reached_review_step=True,
                ready_to_submit=True,
                cta_text="candidatura simplificada",
                modal_sample="review your application | submit application",
            )
        )

        self.assertEqual(inspection.outcome, "ready")
        self.assertIn("revisao_final_alcancada=sim", inspection.detail)
        self.assertIn("pronto_para_envio=sim", inspection.detail)

    def test_classify_page_state_blocks_external_apply(self) -> None:
        inspection = classify_linkedin_application_page_state(
            LinkedInApplicationPageState(external_apply=True)
        )

        self.assertEqual(inspection.outcome, "blocked")
        self.assertIn("candidatura externa", inspection.detail)

    def test_classify_page_state_marks_unopened_easy_apply_as_manual_review(self) -> None:
        inspection = classify_linkedin_application_page_state(
            LinkedInApplicationPageState(easy_apply=True, cta_text="easy apply", sample="easy apply | company | vaga")
        )

        self.assertEqual(inspection.outcome, "manual_review")
        self.assertIn("modal nao abriu", inspection.detail)
        self.assertIn("cta=easy apply", inspection.detail)

    def test_describe_linkedin_modal_blocker_lists_pending_signals(self) -> None:
        blocker = describe_linkedin_modal_blocker(
            LinkedInApplicationPageState(
                modal_open=True,
                modal_next_visible=True,
                modal_file_upload=True,
                modal_questions_visible=True,
                resumable_fields=("telefone",),
            )
        )

        self.assertIn("perguntas_obrigatorias", blocker)
        self.assertIn("upload_cv_pendente", blocker)
        self.assertIn("etapa_intermediaria", blocker)
        self.assertIn("botao_submit_ausente", blocker)
        self.assertIn("campos_nao_preenchidos", blocker)

    def test_describe_linkedin_modal_blocker_marks_save_application_confirmation(self) -> None:
        blocker = describe_linkedin_modal_blocker(
            LinkedInApplicationPageState(
                modal_open=False,
                save_application_dialog_visible=True,
            )
        )

        self.assertIn("confirmacao_salvar_candidatura", blocker)

    def test_build_linkedin_modal_snapshot_uses_headings_buttons_and_fields(self) -> None:
        snapshot = build_linkedin_modal_snapshot(
            LinkedInApplicationPageState(
                modal_open=True,
                modal_headings=("informacoes de contato", "curriculo"),
                modal_buttons=("next", "review", "submit application"),
                modal_fields=("email", "phone", "country code"),
            )
        )

        self.assertIn("titulos=informacoes de contato, curriculo", snapshot)
        self.assertIn("botoes=next, review, submit application", snapshot)
        self.assertIn("campos_detectados=email, phone, country code", snapshot)

    def test_describe_linkedin_easy_apply_entrypoint_uses_cta_and_page_sample(self) -> None:
        detail = describe_linkedin_easy_apply_entrypoint(
            LinkedInApplicationPageState(
                easy_apply=True,
                cta_text="easy apply",
                sample="easy apply | empresa teste | vaga teste",
            )
        )

        self.assertIn("cta=easy apply", detail)
        self.assertIn("pagina=easy apply | empresa teste | vaga teste", detail)

    def test_format_modal_interpretation_for_error_includes_structured_hint(self) -> None:
        inspector = LinkedInApplicationFlowInspector(
            storage_state_path="linkedin_state.json",
            headless=True,
        )

        detail = inspector._format_modal_interpretation_for_error(
            LinkedInApplicationPageState(
                modal_open=True,
                modal_submit_visible=True,
                ready_to_submit=True,
            )
        )

        self.assertIn("interpretacao_modal=", detail)
        self.assertIn("acao=submit_if_authorized", detail)

    def test_capture_failure_artifacts_writes_html_and_metadata(self) -> None:
        class _Page:
            async def content(self):
                return "<html><body>teste</body></html>"

            async def screenshot(self, path, full_page):
                Path(path).write_bytes(b"fake-png")

        class _Job:
            id = 999
            title = "Backend Engineer"
            url = "https://www.linkedin.com/jobs/view/999/"

        tmp = prepare_workspace_tmp_dir("linkedin-artifacts")
        try:
            inspector = LinkedInApplicationFlowInspector(
                storage_state_path="linkedin_state.json",
                headless=True,
                save_failure_artifacts=True,
                failure_artifacts_dir=tmp,
            )
            import asyncio

            detail = asyncio.run(
                inspector._capture_failure_artifacts(
                    _Page(),
                    state=LinkedInApplicationPageState(
                        easy_apply=True,
                        modal_open=False,
                        cta_text="candidatura simplificada",
                    ),
                    job=_Job(),
                    phase="submit",
                    detail="falha de teste",
                )
            )

            files = list(Path(tmp).iterdir())
            self.assertTrue(any(path.suffix == ".html" for path in files))
            self.assertTrue(any(path.suffix == ".json" for path in files))
            self.assertTrue(any(path.suffix == ".png" for path in files))
            self.assertIn("artefatos=", detail)
        finally:
            pass
