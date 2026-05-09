import sqlite3
import unittest

from job_hunter_agent.application.human_review import (
    APPROVED,
    AUTHORIZED_FOR_EXTERNAL_ACTION,
    BLOCKED,
    PENDING_REVIEW,
    REJECTED,
    is_external_action_authorized,
    resolve_human_review_decision,
)
from job_hunter_agent.infrastructure.application_history import (
    list_application_events,
    record_application_event,
)
from job_hunter_agent.infrastructure.schema_migrations import ensure_current_schema_version


class HumanReviewDecisionTests(unittest.TestCase):
    def test_approve_records_human_actor_reason_and_timestamp(self) -> None:
        decision = resolve_human_review_decision(
            application_id=42,
            current_state=PENDING_REVIEW,
            action="approve",
            decided_by="vinicius",
            reason="vaga aderente ao perfil",
            decided_at_utc="2026-05-07T12:00:00+00:00",
        )

        self.assertEqual(decision.application_id, 42)
        self.assertEqual(decision.from_state, PENDING_REVIEW)
        self.assertEqual(decision.to_state, APPROVED)
        self.assertEqual(decision.decided_by, "vinicius")
        self.assertEqual(decision.reason, "vaga aderente ao perfil")
        self.assertEqual(decision.decided_at_utc, "2026-05-07T12:00:00+00:00")
        self.assertFalse(decision.allows_external_action)

    def test_reject_requires_audit_reason(self) -> None:
        decision = resolve_human_review_decision(
            application_id=42,
            current_state=PENDING_REVIEW,
            action="reject",
            decided_by="vinicius",
            reason="senioridade fora do alvo",
        )

        self.assertEqual(decision.to_state, REJECTED)
        self.assertEqual(decision.reason, "senioridade fora do alvo")
        self.assertFalse(decision.allows_external_action)

    def test_block_records_safety_decision(self) -> None:
        decision = resolve_human_review_decision(
            application_id=42,
            current_state=PENDING_REVIEW,
            action="block",
            decided_by="vinicius",
            reason="exige envio de dados sensíveis fora do fluxo",
        )

        self.assertEqual(decision.to_state, BLOCKED)
        self.assertFalse(decision.allows_external_action)

    def test_external_action_requires_prior_approval(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "external action can only be authorized after approval",
        ):
            resolve_human_review_decision(
                application_id=42,
                current_state=PENDING_REVIEW,
                action="authorize_external_action",
                decided_by="vinicius",
                reason="pode submeter",
            )

    def test_authorize_external_action_after_approval(self) -> None:
        decision = resolve_human_review_decision(
            application_id=42,
            current_state=APPROVED,
            action="authorize_external_action",
            decided_by="vinicius",
            reason="revisado e autorizado para envio",
        )

        self.assertEqual(decision.to_state, AUTHORIZED_FOR_EXTERNAL_ACTION)
        self.assertTrue(decision.allows_external_action)
        self.assertTrue(is_external_action_authorized(decision.to_state))

    def test_decision_exposes_auditable_event_payload(self) -> None:
        decision = resolve_human_review_decision(
            application_id=42,
            current_state=APPROVED,
            action="authorize_external_action",
            decided_by="vinicius",
            reason="revisado e autorizado para envio",
            decided_at_utc="2026-05-07T12:30:00+00:00",
        )

        self.assertEqual(decision.event_type, "human_review_authorize_external_action")
        self.assertEqual(
            decision.to_event_payload(),
            {
                "from_state": APPROVED,
                "to_state": AUTHORIZED_FOR_EXTERNAL_ACTION,
                "action": "authorize_external_action",
                "decided_by": "vinicius",
                "reason": "revisado e autorizado para envio",
                "decided_at_utc": "2026-05-07T12:30:00+00:00",
                "allows_external_action": True,
            },
        )

    def test_decision_payload_can_be_recorded_in_application_history(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE job_applications (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO job_applications (id) VALUES (42)")
        ensure_current_schema_version(connection)
        decision = resolve_human_review_decision(
            application_id=42,
            current_state=PENDING_REVIEW,
            action="reject",
            decided_by="vinicius",
            reason="fora do alvo atual",
            decided_at_utc="2026-05-07T12:45:00+00:00",
        )

        record_application_event(
            connection,
            application_id=decision.application_id,
            event_type=decision.event_type,
            payload=decision.to_event_payload(),
            occurred_at_utc=decision.decided_at_utc,
        )

        events = list_application_events(connection, 42)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "human_review_reject")
        self.assertEqual(events[0].occurred_at_utc, "2026-05-07T12:45:00+00:00")
        self.assertEqual(events[0].payload["to_state"], REJECTED)
        self.assertEqual(events[0].payload["reason"], "fora do alvo atual")
        self.assertFalse(events[0].payload["allows_external_action"])

    def test_automation_cannot_decide_human_review(self) -> None:
        with self.assertRaisesRegex(ValueError, "human reviewer, not automation"):
            resolve_human_review_decision(
                application_id=42,
                current_state=PENDING_REVIEW,
                action="approve",
                decided_by="bot",
                reason="auto approve",
            )

    def test_reason_is_required_for_auditability(self) -> None:
        with self.assertRaisesRegex(ValueError, "reason is required"):
            resolve_human_review_decision(
                application_id=42,
                current_state=PENDING_REVIEW,
                action="reject",
                decided_by="vinicius",
                reason=" ",
            )

    def test_terminal_states_cannot_be_changed(self) -> None:
        with self.assertRaisesRegex(ValueError, "already finalized"):
            resolve_human_review_decision(
                application_id=42,
                current_state=REJECTED,
                action="approve",
                decided_by="vinicius",
                reason="reabrir",
            )


if __name__ == "__main__":
    unittest.main()
