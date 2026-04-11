import unittest
from unittest.mock import patch


class CompositionInjectionTests(unittest.TestCase):
    def test_create_linkedin_application_flow_inspector_injects_artifact_capture(self) -> None:
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

        with patch(
            "job_hunter_agent.application.composition.load_candidate_profile",
            return_value=candidate_profile,
        ) as load_profile, patch(
            "job_hunter_agent.application.composition.LinkedInApplicationFlowInspector",
            return_value="inspector",
        ) as inspector_factory:
            from job_hunter_agent.application.composition import create_linkedin_application_flow_inspector

            create_linkedin_application_flow_inspector(settings, mode="preflight")

        # Confirma que artifact_capture foi passado como kwarg
        kwargs = inspector_factory.call_args.kwargs  # type: ignore[attr-defined]
        self.assertIn("artifact_capture", kwargs)
        self.assertTrue(kwargs["artifact_capture"].enabled)
        self.assertEqual(str(kwargs["artifact_capture"].artifacts_dir), ".tmp-tests/failure-artifacts")
        load_profile.assert_called_once_with("candidate_profile.json")
