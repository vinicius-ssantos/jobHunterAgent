import unittest
from unittest.mock import patch


class CompositionInjectionTests(unittest.TestCase):
    def test_create_linkedin_preflight_inspector_injects_artifact_capture(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "linkedin_storage_state_path": "linkedin-state.json",
                "browser_headless": True,
                "resume_path": "resume.pdf",
                "application_contact_email": "vinicius@example.com",
                "application_phone": "11999999999",
                "application_phone_country_code": "55",
                "candidate_profile_path": "candidate_profile.json",
                "save_failure_artifacts": True,
                "failure_artifacts_dir": ".tmp-tests/failure-artifacts",
                "linkedin_modal_llm_enabled": False,
                "ollama_model": "llama3",
                "ollama_url": "http://localhost:11434",
            },
        )()

        candidate_profile = object()
        sentinel_inspector = object()

        with patch(
            "job_hunter_agent.application.composition.load_candidate_profile",
            return_value=candidate_profile,
        ) as load_profile, patch(
            "job_hunter_agent.application.composition.LinkedInApplicationFlowInspector",
            return_value=sentinel_inspector,
        ) as inspector_factory:
            from job_hunter_agent.application.composition import create_linkedin_preflight_inspector

            adapter = create_linkedin_preflight_inspector(settings)

        kwargs = inspector_factory.call_args.kwargs  # type: ignore[attr-defined]
        self.assertIn("artifact_capture", kwargs)
        self.assertTrue(kwargs["artifact_capture"].enabled)
        self.assertEqual(str(kwargs["artifact_capture"].artifacts_dir), ".tmp-tests/failure-artifacts")
        self.assertIs(adapter._inspector, sentinel_inspector)
        load_profile.assert_called_once_with("candidate_profile.json")

    def test_create_linkedin_submission_applicant_wraps_submit_mode_inspector(self) -> None:
        settings = type(
            "Settings",
            (),
            {
                "linkedin_storage_state_path": "linkedin-state.json",
                "browser_headless": True,
                "resume_path": "resume.pdf",
                "application_contact_email": "vinicius@example.com",
                "application_phone": "11999999999",
                "application_phone_country_code": "55",
                "candidate_profile_path": "candidate_profile.json",
                "save_failure_artifacts": True,
                "failure_artifacts_dir": ".tmp-tests/failure-artifacts",
                "linkedin_modal_llm_enabled": False,
                "ollama_model": "llama3",
                "ollama_url": "http://localhost:11434",
            },
        )()

        with patch(
            "job_hunter_agent.application.composition.load_candidate_profile",
            return_value=object(),
        ), patch(
            "job_hunter_agent.application.composition.LinkedInApplicationFlowInspector",
            return_value=object(),
        ) as inspector_factory:
            from job_hunter_agent.application.composition import create_linkedin_submission_applicant

            adapter = create_linkedin_submission_applicant(settings)

        kwargs = inspector_factory.call_args.kwargs  # type: ignore[attr-defined]
        self.assertIn("modal_interpreter", kwargs)
        self.assertFalse(hasattr(adapter, "inspect"))
        self.assertTrue(hasattr(adapter, "submit"))
