from unittest import TestCase

from job_hunter_agent.domain import JobPosting
from job_hunter_agent.notifier import NullNotifier, build_job_card_message, build_missing_job_reply, resolve_review_action


def sample_job(status: str = "collected") -> JobPosting:
    return JobPosting(
        title="Senior Kotlin Engineer",
        company="ACME",
        location="Brasil",
        work_mode="remoto",
        salary_text="Nao informado",
        url="https://example.com/job-1",
        source_site="LinkedIn",
        summary="Resumo",
        relevance=8,
        rationale="Boa aderencia ao perfil.",
        external_key="key-1",
        id=1,
        status=status,
    )


class ReviewActionTests(TestCase):
    def test_approve_collected_job(self) -> None:
        next_status, reply = resolve_review_action(sample_job(), "approve")
        self.assertEqual(next_status, "approved")
        self.assertIn("aprovada", reply)

    def test_reject_collected_job(self) -> None:
        next_status, reply = resolve_review_action(sample_job(), "reject")
        self.assertEqual(next_status, "rejected")
        self.assertIn("ignorada", reply)

    def test_prevent_duplicate_approval(self) -> None:
        next_status, reply = resolve_review_action(sample_job(status="approved"), "approve")
        self.assertIsNone(next_status)
        self.assertIn("ja estava aprovada", reply)

    def test_invalid_action_is_rejected(self) -> None:
        next_status, reply = resolve_review_action(sample_job(), "archive")
        self.assertIsNone(next_status)
        self.assertIn("invalida", reply)

    def test_build_job_card_message_contains_essential_fields(self) -> None:
        message = build_job_card_message(sample_job())

        self.assertIn("Senior Kotlin Engineer", message)
        self.assertIn("Empresa: ACME", message)
        self.assertIn("Modalidade: remoto", message)
        self.assertIn("Relevancia: 8/10", message)
        self.assertIn("Abrir vaga", message)

    def test_build_missing_job_reply_is_safe(self) -> None:
        reply = build_missing_job_reply(999)

        self.assertIn("nao encontrada", reply)
        self.assertIn("999", reply)


class NullNotifierTests(TestCase):
    def test_null_notifier_can_be_instantiated(self) -> None:
        notifier = NullNotifier()

        self.assertIsNotNone(notifier)
