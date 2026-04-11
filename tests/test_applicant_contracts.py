import unittest

from job_hunter_agent.application.applicant import (
    normalize_application_flow_inspection,
    normalize_application_submission_result,
)


class ApplicantContractTests(unittest.TestCase):
    def test_normalize_application_flow_inspection_accepts_structural_result(self) -> None:
        result = normalize_application_flow_inspection(
            type("Inspection", (), {"outcome": "ready", "detail": "preflight real ok"})()
        )

        self.assertEqual(result.outcome, "ready")
        self.assertEqual(result.detail, "preflight real ok")

    def test_normalize_application_flow_inspection_rejects_invalid_outcome(self) -> None:
        result = normalize_application_flow_inspection(
            type("Inspection", (), {"outcome": "weird", "detail": "abc"})()
        )

        self.assertEqual(result.outcome, "error")
        self.assertIn("outcome invalido", result.detail)

    def test_normalize_application_submission_result_accepts_structural_result(self) -> None:
        result = normalize_application_submission_result(
            type(
                "SubmitResult",
                (),
                {
                    "status": "submitted",
                    "detail": "submissao real concluida",
                    "submitted_at": "2026-04-05T10:00:00",
                    "external_reference": "abc",
                },
            )()
        )

        self.assertEqual(result.status, "submitted")
        self.assertEqual(result.submitted_at, "2026-04-05T10:00:00")
        self.assertEqual(result.external_reference, "abc")

    def test_normalize_application_submission_result_rejects_empty_detail(self) -> None:
        result = normalize_application_submission_result(
            type("SubmitResult", (), {"status": "submitted", "detail": ""})()
        )

        self.assertEqual(result.status, "error_submit")
        self.assertIn("detail vazio", result.detail)
