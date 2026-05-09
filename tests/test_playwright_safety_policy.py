import unittest

from job_hunter_agent.application.playwright_safety_policy import (
    ALLOWED,
    BLOCKED,
    DRY_RUN_ONLY,
    HUMAN_GATE_REQUIRED,
    ensure_playwright_action_allowed,
    resolve_playwright_policy,
)


class PlaywrightSafetyPolicyTests(unittest.TestCase):
    def test_read_only_actions_are_allowed(self) -> None:
        for category in ("read", "navigate", "inspect"):
            with self.subTest(category=category):
                policy = resolve_playwright_policy(category)

                self.assertEqual(policy.decision, ALLOWED)
                self.assertTrue(policy.allows_playwright_execution)
                self.assertFalse(policy.requires_human_gate)

    def test_sensitive_actions_are_blocked_without_human_gate(self) -> None:
        for category in (
            "authenticate",
            "fill_form",
            "upload_document",
            "submit",
            "send_message",
            "external_contact",
        ):
            with self.subTest(category=category):
                policy = resolve_playwright_policy(category)

                self.assertEqual(policy.decision, BLOCKED)
                self.assertTrue(policy.blocks_external_action)

    def test_sensitive_actions_are_dry_run_only_when_dry_run(self) -> None:
        policy = resolve_playwright_policy("submit", dry_run=True)

        self.assertEqual(policy.decision, DRY_RUN_ONLY)
        self.assertFalse(policy.allows_playwright_execution)

    def test_sensitive_actions_record_human_gate_requirement_when_approved(self) -> None:
        policy = resolve_playwright_policy("submit", human_gate_approved=True)

        self.assertEqual(policy.decision, HUMAN_GATE_REQUIRED)
        self.assertTrue(policy.requires_human_gate)
        self.assertTrue(policy.blocks_external_action)

    def test_safe_stop_reasons_block_even_read_actions(self) -> None:
        for reason in ("captcha", "paywall", "unexpected_prompt", "credential_prompt"):
            with self.subTest(reason=reason):
                policy = resolve_playwright_policy("read", safe_stop_reason=reason)

                self.assertEqual(policy.decision, BLOCKED)
                self.assertIn(reason, policy.reason)

    def test_aggressive_delay_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "avoid aggressive automation"):
            resolve_playwright_policy("read", minimum_delay_seconds=0.1)

    def test_ensure_allowed_raises_for_blocked_policy(self) -> None:
        policy = resolve_playwright_policy("submit")

        with self.assertRaisesRegex(PermissionError, "blocked without human gate"):
            ensure_playwright_action_allowed(policy)


if __name__ == "__main__":
    unittest.main()
