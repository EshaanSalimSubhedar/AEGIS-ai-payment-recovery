from datetime import datetime
from typing import Optional


# ==========================================
# Reason-based recovery priors
# ==========================================

REASON_PRIORS = {
    "bank_timeout": 0.85,
    "insufficient_funds": 0.65,
    "network_error": 0.80,
    "card_expired": 0.25,
    "issuer_declined": 0.35,
    "authentication_failed": 0.45,
    "limit_exceeded": 0.30,
    "fraud_review": 0.10,
    "unknown": 0.40,
}


# ==========================================
# Score calculation
# ==========================================

def calculate_recovery_score(
    amount: float,
    failure_reason: str,
    created_at: Optional[datetime] = None,
    customer_history_score: Optional[float] = None,
) -> float:
    """
    Calculate a transparent 0-1 recovery probability score.

    Inputs:
        amount:
            Failed payment amount.

        failure_reason:
            Normalized classifier category.

        created_at:
            Time at which the payment failed.

        customer_history_score:
            Optional historical recovery score if customer
            history becomes available later.

    The current MVP intentionally uses deterministic
    heuristics rather than pretending to have trained
    ML data.
    """

    # --------------------------------------
    # Start with reason-specific prior
    # --------------------------------------

    score = REASON_PRIORS.get(
        failure_reason,
        REASON_PRIORS["unknown"],
    )

    # --------------------------------------
    # Amount adjustment
    # --------------------------------------
    #
    # Smaller payments are generally easier to recover
    # automatically, while very large payments can warrant
    # additional caution.
    #

    if amount <= 500:
        score += 0.08

    elif amount <= 2000:
        score += 0.04

    elif amount <= 10000:
        score += 0.00

    elif amount <= 50000:
        score -= 0.05

    else:
        score -= 0.10

    # --------------------------------------
    # Time-since-failure adjustment
    # --------------------------------------

    if created_at:
        now = datetime.utcnow()

        elapsed_hours = max(
            0,
            (now - created_at).total_seconds() / 3600,
        )

        if elapsed_hours <= 1:
            score += 0.05

        elif elapsed_hours <= 6:
            score += 0.03

        elif elapsed_hours <= 24:
            score += 0.00

        elif elapsed_hours <= 72:
            score -= 0.05

        else:
            score -= 0.10

    # --------------------------------------
    # Customer history
    # --------------------------------------
    #
    # This is optional because the MVP does not yet have
    # a customer-history table.
    #

    if customer_history_score is not None:
        history = max(
            0.0,
            min(1.0, customer_history_score),
        )

        # Blend current signal with historical signal.
        score = (score * 0.70) + (history * 0.30)

    # --------------------------------------
    # Clamp to 0-1
    # --------------------------------------

    return round(
        max(0.0, min(1.0, score)),
        4,
    )


# ==========================================
# Score category
# ==========================================

def score_category(
    score: float,
) -> str:
    """
    Convert a numeric recovery score into a routing tier.
    """

    if score >= 0.70:
        return "high"

    if score >= 0.45:
        return "medium"

    return "low"