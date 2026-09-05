from dataclasses import dataclass
from typing import Optional


# ==========================================
# Action constants
# ==========================================

IMMEDIATE_RETRY = "immediate_retry"

DELAYED_RETRY = "delayed_retry"

PAYMENT_LINK = "payment_link"

HUMAN_REVIEW = "human_review"

ABANDON = "abandon"


@dataclass
class ActionDecision:
    """
    Represents the agent's decision for a failed payment.
    """

    action: str

    reasoning: str

    delay_hours: Optional[float] = None


# ==========================================
# Action planner
# ==========================================

def plan_action(
    failure_reason: str,
    recovery_score: float,
    attempts: int,
    max_attempts: int = 3,
    opted_out: bool = False,
) -> ActionDecision:
    """
    Decide the next recovery action.

    Priority:

        1. Respect opt-out
        2. Enforce stopping rule
        3. Handle high-risk failure types
        4. Route high-probability recoveries
        5. Route medium-probability recoveries
        6. Escalate low-probability cases
    """

    # --------------------------------------
    # 1. Customer opted out
    # --------------------------------------

    if opted_out:
        return ActionDecision(
            action=ABANDON,
            reasoning=(
                "Customer has opted out of further contact. "
                "All automated recovery actions are stopped."
            ),
        )

    # --------------------------------------
    # 2. Maximum attempts reached
    # --------------------------------------

    if attempts >= max_attempts:
        return ActionDecision(
            action=ABANDON,
            reasoning=(
                f"Maximum automated retry limit of "
                f"{max_attempts} attempts has been reached."
            ),
        )

    # --------------------------------------
    # 3. Fraud / risk review
    # --------------------------------------

    if failure_reason == "fraud_review":
        return ActionDecision(
            action=HUMAN_REVIEW,
            reasoning=(
                "Transaction requires risk/fraud review and "
                "should not be automatically retried."
            ),
        )

    # --------------------------------------
    # 4. Expired card
    # --------------------------------------

    if failure_reason == "card_expired":
        return ActionDecision(
            action=PAYMENT_LINK,
            reasoning=(
                "The payment method appears expired. "
                "A new payment link allows the customer to "
                "use an updated payment method."
            ),
        )

    # --------------------------------------
    # 5. Issuer decline
    # --------------------------------------

    if failure_reason == "issuer_declined":
        if recovery_score >= 0.70:
            return ActionDecision(
                action=DELAYED_RETRY,
                delay_hours=2,
                reasoning=(
                    "Issuer decline has a sufficiently high "
                    "recovery score. Retry after the minimum "
                    "cooldown rather than immediately."
                ),
            )

        return ActionDecision(
            action=HUMAN_REVIEW,
            reasoning=(
                "Issuer decline has insufficient recovery "
                "probability for automated retry."
            ),
        )

    # --------------------------------------
    # 6. Bank timeout
    # --------------------------------------

    if failure_reason == "bank_timeout":
        if recovery_score >= 0.70:
            return ActionDecision(
                action=IMMEDIATE_RETRY,
                reasoning=(
                    "Bank/gateway timeout is transient in nature "
                    "and has a high recovery probability."
                ),
            )

        return ActionDecision(
            action=DELAYED_RETRY,
            delay_hours=2,
            reasoning=(
                "Timeout may be transient, but recovery "
                "probability does not justify an immediate retry."
            ),
        )

    # --------------------------------------
    # 7. Network error
    # --------------------------------------

    if failure_reason == "network_error":
        return ActionDecision(
            action=DELAYED_RETRY,
            delay_hours=2,
            reasoning=(
                "Network failure is potentially transient; "
                "retry after the configured cooldown."
            ),
        )

    # --------------------------------------
    # 8. Insufficient funds
    # --------------------------------------

    if failure_reason == "insufficient_funds":
        return ActionDecision(
            action=DELAYED_RETRY,
            delay_hours=24,
            reasoning=(
                "Insufficient funds should not be retried "
                "immediately. Delay the attempt to give the "
                "customer an opportunity to replenish funds."
            ),
        )

    # --------------------------------------
    # 9. Authentication failure
    # --------------------------------------

    if failure_reason == "authentication_failed":
        return ActionDecision(
            action=PAYMENT_LINK,
            reasoning=(
                "Authentication failure is better handled by "
                "providing the customer with a fresh payment flow."
            ),
        )

    # --------------------------------------
    # 10. Limit exceeded
    # --------------------------------------

    if failure_reason == "limit_exceeded":
        return ActionDecision(
            action=HUMAN_REVIEW,
            reasoning=(
                "Transaction limits may require customer or "
                "merchant intervention."
            ),
        )

    # --------------------------------------
    # 11. Generic high-probability case
    # --------------------------------------

    if recovery_score >= 0.70:
        return ActionDecision(
            action=IMMEDIATE_RETRY,
            reasoning=(
                f"Recovery probability is high "
                f"({recovery_score:.0%}), so the agent routes "
                f"the payment to automated recovery."
            ),
        )

    # --------------------------------------
    # 12. Generic medium probability
    # --------------------------------------

    if recovery_score >= 0.45:
        return ActionDecision(
            action=DELAYED_RETRY,
            delay_hours=2,
            reasoning=(
                f"Recovery probability is moderate "
                f"({recovery_score:.0%}), so the agent schedules "
                f"a retry after the cooldown."
            ),
        )

    # --------------------------------------
    # 13. Low probability
    # --------------------------------------

    return ActionDecision(
        action=HUMAN_REVIEW,
        reasoning=(
            f"Recovery probability is low "
            f"({recovery_score:.0%}). Automated retries are "
            f"not justified, so the case is escalated."
        ),
    )