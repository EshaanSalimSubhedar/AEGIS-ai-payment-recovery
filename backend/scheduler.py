from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import (
    BackgroundScheduler,
)
from sqlalchemy.orm import Session

from backend.audit.audit_log import (
    ACTION_BLOCKED,
    PTP_FOLLOW_UP_SENT,
    RETRY_SCHEDULED,
    log_action,
)
from backend.db.models import (
    FailedPayment,
    PromiseToPay,
    SessionLocal,
)
from backend.tracker.stopping_rules import (
    can_execute_automated_action,
)


# ==========================================
# Scheduler
# ==========================================

scheduler = BackgroundScheduler(
    timezone="Asia/Kolkata"
)


# ==========================================
# Retry job
# ==========================================

def execute_scheduled_retry(
    payment_id: int,
):
    """
    Execute a delayed retry.

    The database is re-read immediately before execution so
    an opt-out, recovery, or attempt-limit change that
    happened after scheduling is respected.
    """

    db: Session = SessionLocal()

    try:
        payment = (
            db.query(FailedPayment)
            .filter(
                FailedPayment.id
                == payment_id
            )
            .first()
        )

        if not payment:
            return

        # Import here to avoid circular imports during
        # application startup.
        from backend.app import execute_payment_action, SETTINGS

        max_attempts = SETTINGS[
            "retry"
        ][
            "max_attempts"
        ]

        cooldown_hours = SETTINGS[
            "retry"
        ][
            "cooldown_hours"
        ]

        # --------------------------------------
        # Re-check safety immediately before action
        # --------------------------------------

        allowed, reason = (
            can_execute_automated_action(
                attempts=payment.attempts,
                max_attempts=max_attempts,
                last_attempt_at=payment.last_attempt_at,
                opted_out=payment.opted_out,
                status=payment.status,
                cooldown_hours=cooldown_hours,
            )
        )

        if not allowed:
            log_action(
                db=db,
                payment_id=payment.id,
                action=ACTION_BLOCKED,
                reasoning=(
                    f"Scheduled retry was blocked at "
                    f"execution time: {reason}."
                ),
            )

            return

        # --------------------------------------
        # Execute
        # --------------------------------------

        execute_payment_action(
            db=db,
            payment=payment,
        )

    finally:
        db.close()


# ==========================================
# Schedule retry
# ==========================================

def schedule_retry(
    payment_id: int,
    delay_hours: float,
):
    """
    Schedule a retry.

    A tiny delay is used even for an "immediate" retry so
    the current database transaction/request can finish
    before the background worker starts.
    """

    minimum_delay_seconds = 1

    delay_seconds = max(
        minimum_delay_seconds,
        int(delay_hours * 3600),
    )

    run_at = (
        datetime.now()
        + timedelta(seconds=delay_seconds)
    )

    scheduler.add_job(
        execute_scheduled_retry,
        trigger="date",
        run_date=run_at,
        args=[payment_id],
        id=(
            f"retry-{payment_id}-"
            f"{int(run_at.timestamp())}"
        ),
        replace_existing=True,
    )


# ==========================================
# PTP follow-up
# ==========================================

def execute_ptp_follow_up(
    promise_id: int,
):
    """
    Send the single PTP follow-up.

    The promise is re-read from the database to ensure
    that it still exists and has not already been fulfilled
    or followed up.
    """

    db: Session = SessionLocal()

    try:
        promise = (
            db.query(PromiseToPay)
            .filter(
                PromiseToPay.id
                == promise_id
            )
            .first()
        )

        if not promise:
            return

        if promise.follow_up_sent:
            return

        if promise.fulfilled:
            return

        payment = (
            db.query(FailedPayment)
            .filter(
                FailedPayment.id
                == promise.payment_id
            )
            .first()
        )

        if not payment:
            return

        # --------------------------------------
        # Never contact opted-out customer
        # --------------------------------------

        if payment.opted_out:
            log_action(
                db=db,
                payment_id=payment.id,
                action=ACTION_BLOCKED,
                reasoning=(
                    "PTP follow-up blocked because the "
                    "customer opted out."
                ),
            )

            return

        # --------------------------------------
        # Build message
        # --------------------------------------

        from backend.messaging.llm_composer import (
            get_llm_composer,
        )

        from backend.messaging.channel_dispatcher import (
            get_channel_dispatcher,
        )

        message, fallback_used = (
            get_llm_composer().compose(
                customer_name=payment.customer_name,
                amount=payment.amount,
                failure_reason=payment.failure_reason,
                action="ptp_follow_up",
                language_pref=payment.language_pref,
                payment_link=payment.payment_link,
            )
        )

        if fallback_used:
            log_action(
                db=db,
                payment_id=payment.id,
                action="llm_fallback_used",
                reasoning=(
                    "Groq was unavailable while generating "
                    "the PTP follow-up. Static fallback used."
                ),
            )

        # --------------------------------------
        # Send
        # --------------------------------------

        dispatcher = get_channel_dispatcher()

        dispatcher.send(
            channel="twilio_sms",
            recipient=payment.customer_contact,
            message=message,
        )

        promise.follow_up_sent = True

        db.commit()

        log_action(
            db=db,
            payment_id=payment.id,
            action=PTP_FOLLOW_UP_SENT,
            reasoning=(
                f"Single PTP follow-up sent on the "
                f"promised payment date "
                f"{promise.promised_date.isoformat()}."
            ),
        )

    finally:
        db.close()


# ==========================================
# Schedule PTP
# ==========================================

def schedule_ptp_follow_up(
    promise_id: int,
    run_at: datetime,
):
    """
    Schedule exactly one PTP follow-up.
    """

    scheduler.add_job(
        execute_ptp_follow_up,
        trigger="date",
        run_date=run_at,
        args=[promise_id],
        id=f"ptp-{promise_id}",
        replace_existing=True,
    )


# ==========================================
# Start scheduler
# ==========================================

def start_scheduler():
    """
    Start APScheduler if it is not already running.
    """

    if not scheduler.running:
        scheduler.start()


# ==========================================
# Stop scheduler
# ==========================================

def stop_scheduler():
    """
    Shut down APScheduler gracefully.
    """

    if scheduler.running:
        scheduler.shutdown(
            wait=False
        )