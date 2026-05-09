from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

HumanReviewState = Literal[
    "pending_review",
    "approved",
    "rejected",
    "blocked",
    "authorized_for_external_action",
]
HumanReviewAction = Literal["approve", "reject", "block", "authorize_external_action"]

PENDING_REVIEW: HumanReviewState = "pending_review"
APPROVED: HumanReviewState = "approved"
REJECTED: HumanReviewState = "rejected"
BLOCKED: HumanReviewState = "blocked"
AUTHORIZED_FOR_EXTERNAL_ACTION: HumanReviewState = "authorized_for_external_action"

_TERMINAL_STATES: set[HumanReviewState] = {
    REJECTED,
    BLOCKED,
    AUTHORIZED_FOR_EXTERNAL_ACTION,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class HumanReviewDecision:
    application_id: int
    from_state: HumanReviewState
    to_state: HumanReviewState
    action: HumanReviewAction
    decided_by: str
    reason: str
    decided_at_utc: str = field(default_factory=utc_now_iso)

    @property
    def allows_external_action(self) -> bool:
        return self.to_state == AUTHORIZED_FOR_EXTERNAL_ACTION

    @property
    def event_type(self) -> str:
        return f"human_review_{self.action}"

    def to_event_payload(self) -> dict[str, str | bool]:
        return {
            "from_state": self.from_state,
            "to_state": self.to_state,
            "action": self.action,
            "decided_by": self.decided_by,
            "reason": self.reason,
            "decided_at_utc": self.decided_at_utc,
            "allows_external_action": self.allows_external_action,
        }


def require_explicit_human_actor(decided_by: str) -> str:
    actor = decided_by.strip()
    if not actor:
        raise ValueError("decided_by must identify the human reviewer")
    if actor.lower() in {"system", "automation", "auto", "bot"}:
        raise ValueError("decided_by must be a human reviewer, not automation")
    return actor


def require_reason(reason: str, *, action: HumanReviewAction) -> str:
    clean_reason = reason.strip()
    if not clean_reason:
        raise ValueError(f"reason is required to {action}")
    return clean_reason


def resolve_human_review_decision(
    *,
    application_id: int,
    current_state: HumanReviewState,
    action: HumanReviewAction,
    decided_by: str,
    reason: str,
    decided_at_utc: str | None = None,
) -> HumanReviewDecision:
    if application_id <= 0:
        raise ValueError("application_id must be positive")

    actor = require_explicit_human_actor(decided_by)
    clean_reason = require_reason(reason, action=action)

    if current_state in _TERMINAL_STATES:
        raise ValueError(f"human review already finalized: {current_state}")

    if action == "approve":
        to_state: HumanReviewState = APPROVED
    elif action == "reject":
        to_state = REJECTED
    elif action == "block":
        to_state = BLOCKED
    elif action == "authorize_external_action":
        if current_state != APPROVED:
            raise ValueError("external action can only be authorized after approval")
        to_state = AUTHORIZED_FOR_EXTERNAL_ACTION
    else:
        raise ValueError(f"unsupported human review action: {action}")

    return HumanReviewDecision(
        application_id=application_id,
        from_state=current_state,
        to_state=to_state,
        action=action,
        decided_by=actor,
        reason=clean_reason,
        decided_at_utc=decided_at_utc or utc_now_iso(),
    )


def is_external_action_authorized(state: HumanReviewState) -> bool:
    return state == AUTHORIZED_FOR_EXTERNAL_ACTION
