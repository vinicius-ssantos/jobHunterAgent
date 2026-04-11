import unittest

from job_hunter_agent.application.application_ports import (
    normalize_application_flow_inspection,
    normalize_application_submission_result,
)


class ApplicationPortsTests(unittest.TestCase):
    def test_normalize_application_flow_inspection_rejects_invalid_outcome(self) -> None:
        result = normalize_application_flow_inspection(
            type("Inspection", (), {"outcome": "weird", "detail": "algo"})()
        )

        self.assertEqual(result.outcome, "error")
        self.assertIn("outcome invalido", result.detail)

    def test_normalize_application_submission_result_preserves_external_reference(self) -> None:
        result = normalize_application_submission_result(
            type(
                "Submission",
                (),
                {
                    "status": "submitted",
                    "detail": "ok",
                    "submitted_at": "2026-04-11T19:00:00",
                    "external_reference": "linkedin-123",
                },
            )()
        )

        self.assertEqual(result.status, "submitted")
        self.assertEqual(result.external_reference, "linkedin-123")
        self.assertEqual(result.submitted_at, "2026-04-11T19:00:00")
