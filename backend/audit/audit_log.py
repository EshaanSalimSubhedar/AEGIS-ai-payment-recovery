from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.db.models import AuditLog


# ==========================================
# Audit action constants
# ==========================================

PAYMENT_INGESTED = "payment_ingested"

FAILURE_CLASSIFIED = "failure_classified"

RECOVERY_SCORED = "recovery_scored"

ACTION_PLANNED = "action_planned"

RETRY_SCHEDULED = "retry_scheduled"

RETRY_EXECUTED = "retry_executed"

PAYMENT_LINK_CREATED = "payment_link_created"

MESSAGE_GENERATED = "message_generated"

MESSAGE_SENT = "message_sent"

LLM_FALLBACK_USED = "llm_fallback_used"

PTP_DETECTED = "ptp_detected"

PTP_FOLLOW_UP_SCHEDULED = "ptp_follow_up_scheduled"

PTP_FOLLOW_UP_SENT = "ptp_follow_up_sent"

OPT_OUT_RECEIVED = "opt_out_received"

ACTION_BLOCKED = "action_blocked"

ABANDONED = "abandoned"

ESCALATED = "escalated"

PAYMENT_RECOVERED = "payment_recovered"

API_ERROR = "api_error"

EXCEPTION = "exception"


# ==========================================
# Create audit entry
# ==========================================

def log_action(
    db: Session,
    payment_id: int,
    action: str,
    reasoning: str,
    timestamp: Optional[datetime] = None,
) -> AuditLog:
    """
    Write a structured audit entry.

    Every important agent decision should pass through
    this function.

    The entry is committed immediately so that the audit
    record exists before a subsequent money-related
    operation is executed.
    """

    audit_entry = AuditLog(
        payment_id=payment_id,
        action=action,
        reasoning=reasoning,
        timestamp=timestamp or datetime.utcnow(),
    )

    db.add(audit_entry)

    # Commit immediately.
    #
    # This is intentional. The hackathon specification
    # requires money-related actions to be logged BEFORE
    # execution.
    db.commit()

    db.refresh(audit_entry)

    return audit_entry


# ==========================================
# Pre-action audit
# ==========================================

def log_pre_action(
    db: Session,
    payment_id: int,
    action: str,
    reasoning: str,
) -> AuditLog:
    """
    Explicit helper for actions that can move money,
    trigger a payment retry, or create a payment link.

    Example:

        log_pre_action(
            db,
            payment.id,
            RETRY_SCHEDULED,
            "Recovery score is 0.84 and failure reason "
            "is bank_timeout."
        )

        execute_retry(...)
    """

    return log_action(
        db=db,
        payment_id=payment_id,
        action=action,
        reasoning=reasoning,
    )


# ==========================================
# Post-action audit
# ==========================================

def log_outcome(
    db: Session,
    payment_id: int,
    action: str,
    reasoning: str,
) -> AuditLog:
    """
    Record the outcome of an action after execution.

    This is separate from log_pre_action() so the audit
    trail can clearly distinguish:

        decision -> execution -> outcome
    """

    return log_action(
        db=db,
        payment_id=payment_id,
        action=action,
        reasoning=reasoning,
    )


# ==========================================
# Retrieve audit trail
# ==========================================

def get_payment_audit(
    db: Session,
    payment_id: int,
) -> list[AuditLog]:
    """
    Return the complete audit trail for one payment,
    ordered chronologically.
    """

    return (
        db.query(AuditLog)
        .filter(AuditLog.payment_id == payment_id)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )