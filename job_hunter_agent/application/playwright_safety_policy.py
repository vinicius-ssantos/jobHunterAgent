from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


BrowserActionCategory = Literal[
    "read",
    "navigate",
    "inspect",
    "authenticate",
    "fill_form",
    "upload_document",
    "submit",
    "send_message",
    "external_contact",
]

BrowserPolicyDecision = Literal["allowed", "dry_run_only", "human_gate_required", "blocked"]

ALLOWED: BrowserPolicyDecision = "allowed"
DRY_RUN_ONLY: BrowserPolicyDecision = "dry_run_only"
HUMAN_GATE_REQUIRED: BrowserPolicyDecision = "human_gate_required"
BLOCKED: BrowserPolicyDecision = "blocked"

SENSITIVE_ACTIONS: set[BrowserActionCategory] = {
    "authenticate",
    "fill_form",
    "upload_document",
    "submit",
    "send_message",
    "external_contact",
}
SAFE_READ_ACTIONS: set[BrowserActionCategory] = {"read", "navigate", "inspect"}
SAFE_STOP_REASONS = {
    "captcha",
    "paywall",
    "blocked",
    "consent_screen",
    "unexpected_prompt",
    "unexpected_login",
    "credential_prompt",
}


@dataclass(frozen=True)
class BrowserActionPolicy:
    category: BrowserActionCategory
    decision: BrowserPolicyDecision
    reason: str
    minimum_delay_seconds: float = 1.0

    @property
    def allows_playwright_execution(self) -> bool:
        return self.decision == ALLOWED

    @property
    def requires_human_gate(self) -> bool:
        return self.decision == HUMAN_GATE_REQUIRED

    @property
    def blocks_external_action(self) -> bool:
        return self.category in SENSITIVE_ACTIONS and self.decision != ALLOWED


def resolve_playwright_policy(
    category: BrowserActionCategory,
    *,
    human_gate_approved: bool = False,
    dry_run: bool = False,
    safe_stop_reason: str | None = None,
    minimum_delay_seconds: float = 1.0,
) -> BrowserActionPolicy:
    if minimum_delay_seconds < 0.5:
        raise ValueError("minimum_delay_seconds must be at least 0.5 to avoid aggressive automation")

    if safe_stop_reason is not None:
        clean_reason = safe_stop_reason.strip().lower()
        if clean_reason in SAFE_STOP_REASONS:
            return BrowserActionPolicy(
                category=category,
                decision=BLOCKED,
                reason=f"safe stop required: {clean_reason}",
                minimum_delay_seconds=minimum_delay_seconds,
            )

    if category in SAFE_READ_ACTIONS:
        return BrowserActionPolicy(
            category=category,
            decision=ALLOWED,
            reason="read-only browser action",
            minimum_delay_seconds=minimum_delay_seconds,
        )

    if dry_run:
        return BrowserActionPolicy(
            category=category,
            decision=DRY_RUN_ONLY,
            reason="sensitive browser action limited to dry-run",
            minimum_delay_seconds=minimum_delay_seconds,
        )

    if category in SENSITIVE_ACTIONS:
        if human_gate_approved:
            return BrowserActionPolicy(
                category=category,
                decision=HUMAN_GATE_REQUIRED,
                reason="sensitive browser action requires human gate; approval recorded",
                minimum_delay_seconds=minimum_delay_seconds,
            )
        return BrowserActionPolicy(
            category=category,
            decision=BLOCKED,
            reason="sensitive browser action blocked without human gate",
            minimum_delay_seconds=minimum_delay_seconds,
        )

    return BrowserActionPolicy(
        category=category,
        decision=BLOCKED,
        reason="out-of-policy browser action",
        minimum_delay_seconds=minimum_delay_seconds,
    )


def ensure_playwright_action_allowed(policy: BrowserActionPolicy) -> None:
    if not policy.allows_playwright_execution:
        raise PermissionError(policy.reason)
