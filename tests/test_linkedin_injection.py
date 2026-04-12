import unittest
from pathlib import Path

from job_hunter_agent.collectors.linkedin_application import LinkedInApplicationFlowInspector
from job_hunter_agent.collectors.linkedin_application_adapters import (
    LinkedInPreflightInspectorAdapter,
    LinkedInSubmissionApplicantAdapter,
)
from job_hunter_agent.collectors.linkedin_application_artifacts import LinkedInFailureArtifactCapture


class LinkedInInjectionTests(unittest.TestCase):
    def test_inspector_accepts_injected_artifact_capture(self) -> None:
        injected = LinkedInFailureArtifactCapture(enabled=True, artifacts_dir=Path(".tmp-tests/failure-artifacts"))

        inspector = LinkedInApplicationFlowInspector(
            storage_state_path="linkedin-state.json",
            headless=True,
            resume_path=None,
            contact_email="",
            phone="",
            phone_country_code="",
            candidate_profile=None,
            candidate_profile_path=None,
            save_failure_artifacts=False,
            failure_artifacts_dir=".tmp-tests/failure-artifacts",
            artifact_capture=injected,
        )

        self.assertIs(inspector._artifact_capture, injected)  # type: ignore[attr-defined]

    def test_preflight_adapter_ignores_non_linkedin_job_before_touching_inspector(self) -> None:
        adapter = LinkedInPreflightInspectorAdapter(object())

        result = adapter.inspect(type("Job", (), {"url": "https://example.com/jobs/123"})())

        self.assertEqual(result.outcome, "ignored")
        self.assertIn("fluxo interno do LinkedIn", result.detail)

    def test_submission_adapter_reports_missing_session_before_submit(self) -> None:
        adapter = LinkedInSubmissionApplicantAdapter(
            object(),
            storage_state_path=".tmp-tests/inexistente-state.json",
        )

        result = adapter.submit(
            object(),
            type("Job", (), {"url": "https://www.linkedin.com/jobs/view/123/"})(),
        )

        self.assertEqual(result.status, "error_submit")
        self.assertIn("sessao autenticada do LinkedIn nao encontrada", result.detail)
