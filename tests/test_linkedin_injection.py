import unittest
from pathlib import Path

from job_hunter_agent.collectors.linkedin_application import LinkedInApplicationFlowInspector
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
            save_failure_artifacts=False,  # default would be False, but we inject anyway
            failure_artifacts_dir=".tmp-tests/failure-artifacts",
            artifact_capture=injected,
        )

        # Garante que a instância injetada é utilizada internamente
        self.assertIs(inspector._artifact_capture, injected)  # type: ignore[attr-defined]

