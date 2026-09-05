from __future__ import annotations

import inspect
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text

from backend.audit.audit_log import (
    ABANDONED,
    ACTION_BLOCKED,
    ACTION_PLANNED,
    API_ERROR,
    ESCALATED,
    FAILURE_CLASSIFIED,
    LLM_FALLBACK_USED,
    MESSAGE_GENERATED,
    MESSAGE_SENT,
    PAYMENT_INGESTED,
    PAYMENT_LINK_CREATED,
    PAYMENT_RECOVERED,
    RECOVERY_SCORED,
    RETRY_EXECUTED,
    RETRY_SCHEDULED,
    log_action,
    log_outcome,
    log_pre_action,
    get_payment_audit,
)

from backend.classifier.rules_engine import classify_failure
from backend.classifier.risk_scorer import (
    calculate_recovery_score,
    score_category,
)
from backend.strategy.action_planner import plan_action

from backend.db.models import (
    FailedPayment,
    SessionLocal,
    init_db,
)

from backend.ingestion.razorpay_connector import (
    RazorpayConnectorError,
    get_razorpay_connector,
)

from backend.messaging.llm_composer import (
    build_fallback_message,
    get_llm_composer,
)
from backend.messaging.channel_dispatcher import (
    MessagingError,
    send_message,
)

from backend.tracker.stopping_rules import (
    can_attempt_recovery,
    get_block_reason,
)

from backend.scheduler import (
    start_scheduler,
    stop_scheduler,
    schedule_retry,
)


# ============================================================
# CONFIG
# ============================================================

MAX_ATTEMPTS = int(
    os.getenv("MAX_RECOVERY_ATTEMPTS", "3")
)

COOLDOWN_HOURS = float(
    os.getenv("RECOVERY_COOLDOWN_HOURS", "2")
)


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    start_scheduler()

    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title="AI Failed-Payment Recovery Agent",
    description=(
        "Autonomous, explainable failed-payment recovery "
        "agent for Razorpay."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class IngestPayload(BaseModel):
    razorpay_payment_id: str = Field(
        min_length=1
    )

    customer_name: str = Field(
        min_length=1
    )

    customer_contact: str = Field(
        min_length=1
    )

    amount: float = Field(
        gt=0
    )

    error_code: Optional[str] = None

    error_description: Optional[str] = None

    language_pref: str = "english"


class WebhookPayload(BaseModel):
    event: Optional[str] = None

    payload: dict[str, Any] = Field(
        default_factory=dict
    )


class CustomerReplyPayload(BaseModel):
    payment_id: int

    message: str = Field(
        min_length=1
    )


# ============================================================
# HELPERS
# ============================================================

def _utc_now() -> datetime:
    return datetime.utcnow()


def _payment_dict(payment: FailedPayment) -> dict[str, Any]:
    return {
        "id": payment.id,
        "razorpay_payment_id": (
            payment.razorpay_payment_id
        ),
        "customer_name": payment.customer_name,
        "customer_contact": payment.customer_contact,
        "language_pref": payment.language_pref,
        "amount": payment.amount,
        "failure_reason": payment.failure_reason,
        "recovery_score": payment.recovery_score,
        "status": payment.status,
        "attempts": payment.attempts,
        "recovery_reference_id": (
            payment.recovery_reference_id
        ),
        "recovery_reference_type": (
            payment.recovery_reference_type
        ),
        "last_attempt_at": (
            payment.last_attempt_at.isoformat()
            if payment.last_attempt_at
            else None
        ),
        "next_action_at": (
            payment.next_action_at.isoformat()
            if payment.next_action_at
            else None
        ),
        "payment_link": payment.payment_link,
        "recovered_at": (
            payment.recovered_at.isoformat()
            if payment.recovered_at
            else None
        ),
        "opted_out": bool(
            payment.opted_out
        ),
        "created_at": (
            payment.created_at.isoformat()
            if payment.created_at
            else None
        ),
        "updated_at": (
            payment.updated_at.isoformat()
            if payment.updated_at
            else None
        ),
    }


def _action_from_plan(
    action: Any,
) -> str:
    if isinstance(action, str):
        return action

    if hasattr(action, "action"):
        return str(action.action)

    return str(action)


def _safe_commit(
    db,
) -> None:
    db.commit()


# ============================================================
# MESSAGE COMPOSITION
# ============================================================

def _compose_recovery_message(
    payment: FailedPayment,
    action: str,
) -> tuple[str, bool]:
    composer = get_llm_composer()

    try:
        return composer.compose(
            customer_name=payment.customer_name,
            amount=payment.amount,
            failure_reason=payment.failure_reason or "unknown",
            action=action,
            language_pref=payment.language_pref or "english",
            payment_link=payment.payment_link,
        )
    except Exception:
        return (
            build_fallback_message(
                customer_name=payment.customer_name,
                amount=payment.amount,
                failure_reason=payment.failure_reason or "unknown",
            ),
            True,
        )


# ============================================================
# MESSAGE DISPATCH
# ============================================================

def _send_recovery_message(
    payment: FailedPayment,
    message: str,
) -> dict[str, Any]:
    """
    Dispatch through the existing Twilio dispatcher.

    Demo mode can still run without Twilio credentials. If the
    dispatcher raises because credentials are absent, the recovery
    action itself is not rolled back; the messaging failure is
    surfaced separately.
    """

    try:
        signature = inspect.signature(
            send_message
        )

        context = {
            "customer_contact": payment.customer_contact,
            "contact": payment.customer_contact,
            "to": payment.customer_contact,
            "phone": payment.customer_contact,
            "message": message,
            "body": message,
            "customer_name": payment.customer_name,
            "payment": payment,
        }

        kwargs = {}

        for parameter_name in signature.parameters:
            if parameter_name in context:
                kwargs[parameter_name] = context[
                    parameter_name
                ]

        result = send_message(
            **kwargs
        )

        return {
            "success": True,
            "result": result,
        }

    except MessagingError as exc:
        return {
            "success": False,
            "error": str(exc),
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }


# ============================================================
# PROCESS INGESTED PAYMENT
# ============================================================

def process_failed_payment(
    db,
    payment: FailedPayment,
) -> str:
    """
    Classify → score → plan.

    Execution is deliberately separate so every money-related
    action can receive a pre-action audit event.
    """

    reason = payment.failure_reason or "unknown"

    score = calculate_recovery_score(
        amount=payment.amount,
        failure_reason=reason,
        created_at=payment.created_at or _utc_now(),
    )
    score_tier = score_category(score)

    payment.recovery_score = score

    log_action(
        db,
        payment.id,
        RECOVERY_SCORED,
        (
            f"Recovery score={score:.2f} ({score_tier}); "
            f"reason={reason}; "
            f"amount=₹{payment.amount:,.2f}"
        ),
    )

    action = _action_from_plan(
        plan_action(
            failure_reason=reason,
            recovery_score=score,
            attempts=payment.attempts or 0,
            max_attempts=MAX_ATTEMPTS,
            opted_out=bool(payment.opted_out),
        )
    )

    log_action(
        db,
        payment.id,
        ACTION_PLANNED,
        (
            f"Planned action={action}; "
            f"reason={reason}; "
            f"score={score:.2f}; "
            f"attempts={payment.attempts}"
        ),
    )

    return action


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
def root():
    return {
        "name": "AI Failed-Payment Recovery Agent",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    demo_mode = (
        os.getenv(
            "RAZORPAY_DEMO_MODE",
            "false",
        ).lower()
        in {"1", "true", "yes", "on"}
    )

    return {
        "status": "ok",
        "razorpay_demo_mode": demo_mode,
        "max_attempts": MAX_ATTEMPTS,
        "cooldown_hours": COOLDOWN_HOURS,
    }


# ============================================================
# INGEST
# ============================================================

@app.post("/ingest")
def ingest(payload: IngestPayload):
    db = SessionLocal()

    try:
        existing = (
            db.query(FailedPayment)
            .filter(
                FailedPayment.razorpay_payment_id
                == payload.razorpay_payment_id
            )
            .first()
        )

        # Idempotency: do not create duplicate cases when the
        # same Razorpay event arrives twice.
        if existing:
            return {
                **_payment_dict(existing),
                "duplicate": True,
            }

        reason = classify_failure(
            payload.error_code,
            payload.error_description,
        )

        now = _utc_now()

        payment = FailedPayment(
            razorpay_payment_id=(
                payload.razorpay_payment_id
            ),
            customer_name=payload.customer_name,
            customer_contact=payload.customer_contact,
            language_pref=payload.language_pref,
            amount=payload.amount,
            failure_reason=reason,
            recovery_score=0.0,
            status="pending",
            attempts=0,
            opted_out=False,
            created_at=now,
            updated_at=now,
        )

        db.add(payment)
        db.commit()
        db.refresh(payment)

        log_action(
            db,
            payment.id,
            PAYMENT_INGESTED,
            (
                f"Failed payment ingested: "
                f"{payload.razorpay_payment_id}; "
                f"amount=₹{payload.amount:,.2f}"
            ),
        )

        log_action(
            db,
            payment.id,
            FAILURE_CLASSIFIED,
            (
                f"Failure classified as "
                f"'{reason}' from "
                f"error_code={payload.error_code!r}; "
                f"description={payload.error_description!r}"
            ),
        )

        action = process_failed_payment(
            db,
            payment,
        )

        # Schedule automatically planned actions.
        if action == "immediate_retry":
            payment.status = "retrying"

            payment.next_action_at = (
                now + timedelta(seconds=1)
            )

            log_action(
                db,
                payment.id,
                RETRY_SCHEDULED,
                (
                    "Immediate recovery retry scheduled "
                    "after transaction commit."
                ),
            )

            db.commit()

            schedule_retry(
                payment.id,
                0,
            )

        elif action == "delayed_retry":
            payment.status = "retrying"

            delay_hours = (
                24
                if reason == "insufficient_funds"
                else COOLDOWN_HOURS
            )

            payment.next_action_at = (
                now
                + timedelta(
                    hours=delay_hours
                )
            )

            log_action(
                db,
                payment.id,
                RETRY_SCHEDULED,
                (
                    f"Delayed recovery scheduled in "
                    f"{delay_hours:g} hours for "
                    f"reason={reason}."
                ),
            )

            db.commit()

            schedule_retry(
                payment.id,
                delay_hours,
            )

        elif action == "human_review":
            payment.status = "escalated"

            log_action(
                db,
                payment.id,
                ESCALATED,
                (
                    "Case routed to human review because "
                    "automated recovery was not sufficiently "
                    "safe or likely to succeed."
                ),
            )

            db.commit()

        elif action == "abandon":
            payment.status = "abandoned"

            log_action(
                db,
                payment.id,
                ABANDONED,
                (
                    "Case abandoned by stopping rules."
                ),
            )

            db.commit()

        else:
            db.commit()

        return {
            **_payment_dict(payment),
            "action": action,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# RAZORPAY WEBHOOK
# ============================================================

@app.post("/webhook")
def razorpay_webhook(payload: WebhookPayload):
    """
    Minimal webhook ingestion endpoint.

    Production signature verification is intentionally outside
    the hackathon MVP scope. Payment correlation is handled using
    explicit recovery references where available.
    """

    event = (
        payload.event
        or "unknown"
    )

    raw = payload.payload

    payment_entity = (
        raw
        .get("payment", {})
        .get("entity", {})
    )

    payment_id = (
        payment_entity.get("id")
        or raw.get("payment_id")
    )

    if not payment_id:
        return {
            "received": True,
            "processed": False,
            "reason": "No payment ID found.",
        }

    status = str(
        payment_entity.get(
            "status",
            "",
        )
    ).lower()

    db = SessionLocal()

    try:
        # First attempt: direct original payment ID.
        payment = (
            db.query(FailedPayment)
            .filter(
                FailedPayment.razorpay_payment_id
                == payment_id
            )
            .first()
        )

        # Second attempt: recovery reference.
        if not payment:
            payment = (
                db.query(FailedPayment)
                .filter(
                    FailedPayment.recovery_reference_id
                    == payment_id
                )
                .first()
            )

        if not payment:
            return {
                "received": True,
                "processed": False,
                "payment_id": payment_id,
                "reason": (
                    "No correlated recovery case."
                ),
            }

        if status in {
            "captured",
            "paid",
            "authorized",
        } or event in {
            "payment.captured",
            "payment.authorized",
        }:
            payment.status = "recovered"
            payment.recovered_at = _utc_now()
            payment.updated_at = _utc_now()

            log_outcome(
                db,
                payment.id,
                PAYMENT_RECOVERED,
                (
                    f"Razorpay webhook confirmed "
                    f"payment recovery: "
                    f"payment_id={payment_id}; "
                    f"event={event}"
                ),
            )

            db.commit()

            return {
                "received": True,
                "processed": True,
                "status": "recovered",
                "payment_id": payment_id,
                "internal_payment_id": payment.id,
            }

        return {
            "received": True,
            "processed": True,
            "status": status or event,
            "payment_id": payment_id,
            "internal_payment_id": payment.id,
        }

    finally:
        db.close()


# ============================================================
# REMOVE DEMO DATA
# ============================================================

@app.delete("/demo-data")
def remove_demo_data():
    db = SessionLocal()

    try:
        demo_rows = (
            db.query(
                FailedPayment.id,
                FailedPayment.amount,
            )
            .filter(
                FailedPayment.razorpay_payment_id.like(
                    "pay_demo_%"
                )
            )
            .all()
        )

        if not demo_rows:
            return {
                "success": True,
                "deleted_count": 0,
                "deleted_amount": 0,
            }

        payment_ids = [
            row.id
            for row in demo_rows
        ]

        deleted_amount = sum(
            float(row.amount or 0)
            for row in demo_rows
        )

        for payment_id in payment_ids:
            db.execute(
                text(
                    "DELETE FROM audit_log "
                    "WHERE payment_id = :payment_id"
                ),
                {
                    "payment_id": payment_id,
                },
            )

            db.execute(
                text(
                    "DELETE FROM promises_to_pay "
                    "WHERE payment_id = :payment_id"
                ),
                {
                    "payment_id": payment_id,
                },
            )

        db.query(FailedPayment).filter(
            FailedPayment.id.in_(payment_ids)
        ).delete(
            synchronize_session=False
        )

        db.commit()

        return {
            "success": True,
            "deleted_count": len(payment_ids),
            "deleted_amount": deleted_amount,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# LIST PAYMENTS
# ============================================================

@app.get("/payments")
def payments():
    db = SessionLocal()

    try:
        rows = (
            db.query(FailedPayment)
            .order_by(
                FailedPayment.updated_at.desc()
            )
            .all()
        )

        return [
            _payment_dict(row)
            for row in rows
        ]

    finally:
        db.close()


# ============================================================
# PAYMENT DETAIL
# ============================================================

@app.get("/payments/{payment_id}")
def payment_detail(
    payment_id: int,
):
    db = SessionLocal()

    try:
        payment = db.get(
            FailedPayment,
            payment_id,
        )

        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Payment not found.",
            )

        return _payment_dict(payment)

    finally:
        db.close()


# ============================================================
# AUDIT
# ============================================================

@app.get("/payments/{payment_id}/audit")
def payment_audit(
    payment_id: int,
):
    db = SessionLocal()

    try:
        payment = db.get(
            FailedPayment,
            payment_id,
        )

        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Payment not found.",
            )

        return get_payment_audit(
            db,
            payment_id,
        )

    finally:
        db.close()


# ============================================================
# EXECUTE RECOVERY ACTION
# ============================================================

def execute_payment_action(
    payment_id: int,
) -> dict[str, Any]:
    db = SessionLocal()

    try:
        payment = db.get(
            FailedPayment,
            payment_id,
        )

        if not payment:
            return {
                "success": False,
                "error": "Payment not found.",
            }

        # ----------------------------------------------------
        # STOPPING RULES
        # ----------------------------------------------------

        if payment.opted_out:
            log_action(
                db,
                payment.id,
                ACTION_BLOCKED,
                "Recovery blocked: customer opted out.",
            )

            return {
                "success": False,
                "blocked": True,
                "reason": "Customer opted out.",
            }

        if payment.status == "recovered":
            return {
                "success": False,
                "blocked": True,
                "reason": "Payment is already recovered.",
            }

        if payment.attempts >= MAX_ATTEMPTS:
            payment.status = "abandoned"

            log_action(
                db,
                payment.id,
                ABANDONED,
                (
                    f"Maximum automated recovery attempts "
                    f"({MAX_ATTEMPTS}) reached."
                ),
            )

            db.commit()

            return {
                "success": False,
                "blocked": True,
                "reason": (
                    "Maximum automated attempts reached."
                ),
            }

        # Cooldown check.
        if payment.last_attempt_at:
            elapsed = (
                _utc_now()
                - payment.last_attempt_at
            )

            if elapsed < timedelta(
                hours=COOLDOWN_HOURS
            ):
                remaining = (
                    timedelta(
                        hours=COOLDOWN_HOURS
                    )
                    - elapsed
                )

                log_action(
                    db,
                    payment.id,
                    ACTION_BLOCKED,
                    (
                        "Recovery blocked by cooldown. "
                        f"Approximately "
                        f"{remaining.total_seconds() / 3600:.2f} "
                        "hours remain."
                    ),
                )

                return {
                    "success": False,
                    "blocked": True,
                    "reason": (
                        "Recovery cooldown is still active."
                    ),
                }

        # ----------------------------------------------------
        # RE-CALCULATE PLAN
        # ----------------------------------------------------

        action = _action_from_plan(
            plan_action(
                failure_reason=payment.failure_reason or "unknown",
                recovery_score=payment.recovery_score or 0.0,
                attempts=payment.attempts or 0,
                max_attempts=MAX_ATTEMPTS,
                opted_out=bool(payment.opted_out),
            )
        )

        # ----------------------------------------------------
        # HUMAN REVIEW
        # ----------------------------------------------------

        if action == "human_review":
            payment.status = "escalated"

            log_pre_action(
                db,
                payment.id,
                ESCALATED,
                (
                    "No automated money movement will occur. "
                    "Case requires human review."
                ),
            )

            db.commit()

            return {
                "success": True,
                "action": "human_review",
                "status": "escalated",
            }

        # ----------------------------------------------------
        # ABANDON
        # ----------------------------------------------------

        if action == "abandon":
            payment.status = "abandoned"

            log_pre_action(
                db,
                payment.id,
                ABANDONED,
                "Stopping rules selected abandonment.",
            )

            db.commit()

            return {
                "success": True,
                "action": "abandon",
                "status": "abandoned",
            }

        # ----------------------------------------------------
        # MONEY-RELATED ACTION
        #
        # REQUIRED: audit BEFORE provider execution.
        # ----------------------------------------------------

        recovery_reference = (
            f"recovery_"
            f"{payment.id}_"
            f"{uuid.uuid4().hex[:10]}"
        )

        if action in {
            "immediate_retry",
            "delayed_retry",
        }:
            log_pre_action(
                db,
                payment.id,
                RETRY_EXECUTED,
                (
                    f"Authorized fresh recovery payment flow "
                    f"for ₹{payment.amount:,.2f}. "
                    f"Original payment="
                    f"{payment.razorpay_payment_id}; "
                    f"attempt={payment.attempts + 1}; "
                    f"action={action}."
                ),
            )

        elif action == "payment_link":
            log_pre_action(
                db,
                payment.id,
                PAYMENT_LINK_CREATED,
                (
                    f"Authorized creation of a new "
                    f"Razorpay Payment Link for "
                    f"₹{payment.amount:,.2f}; "
                    f"reference={recovery_reference}."
                ),
            )

        db.commit()

        # ----------------------------------------------------
        # PROVIDER EXECUTION
        # ----------------------------------------------------

        connector = get_razorpay_connector()

        provider_result: dict[str, Any] = {}

        if action in {
            "immediate_retry",
            "delayed_retry",
        }:
            order = connector.create_recovery_order(
                amount=payment.amount,
                reference_id=recovery_reference,
                currency="INR",
                notes={
                    "failed_payment_id": str(
                        payment.id
                    ),
                    "original_razorpay_payment_id": (
                        payment.razorpay_payment_id
                    ),
                    "failure_reason": (
                        payment.failure_reason
                    ),
                },
            )

            payment.recovery_reference_id = (
                order.order_id
            )
            payment.recovery_reference_type = (
                "razorpay_order"
            )

            provider_result = {
                "type": "order",
                "order_id": order.order_id,
                "amount": order.amount,
                "currency": order.currency,
                "demo_mode": order.demo_mode,
            }

        elif action == "payment_link":
            link = connector.create_payment_link(
                amount=payment.amount,
                customer_name=(
                    payment.customer_name
                ),
                customer_contact=(
                    payment.customer_contact
                ),
                reference_id=recovery_reference,
                description=(
                    "Payment recovery"
                ),
                currency="INR",
            )

            payment.recovery_reference_id = (
                link.link_id
            )
            payment.recovery_reference_type = (
                "razorpay_payment_link"
            )
            payment.payment_link = (
                link.short_url
            )

            provider_result = {
                "type": "payment_link",
                "link_id": link.link_id,
                "short_url": link.short_url,
                "demo_mode": (
                    "demo" in link.link_id
                ),
            }

            log_outcome(
                db,
                payment.id,
                PAYMENT_LINK_CREATED,
                (
                    f"Payment Link created: "
                    f"{link.link_id}; "
                    f"url={link.short_url}"
                ),
            )

        else:
            return {
                "success": False,
                "error": (
                    f"Unsupported recovery action: "
                    f"{action}"
                ),
            }

        # ----------------------------------------------------
        # UPDATE ATTEMPT
        # ----------------------------------------------------

        payment.attempts = (
            payment.attempts + 1
        )

        payment.last_attempt_at = _utc_now()

        payment.updated_at = _utc_now()

        if action == "payment_link":
            payment.status = "pending"
        else:
            payment.status = "retrying"

        db.commit()

        # ----------------------------------------------------
        # MESSAGE GENERATION
        # ----------------------------------------------------

        message, fallback_used = (
            _compose_recovery_message(
                payment,
                action,
            )
        )

        log_action(
            db,
            payment.id,
            MESSAGE_GENERATED,
            (
                f"Recovery message generated; "
                f"fallback_used={fallback_used}"
            ),
        )

        if fallback_used:
            log_action(
                db,
                payment.id,
                LLM_FALLBACK_USED,
                (
                    "Groq message generation was unavailable "
                    "or returned no usable response; "
                    "static recovery template used."
                ),
            )

        # ----------------------------------------------------
        # MESSAGE DELIVERY
        # ----------------------------------------------------

        delivery = _send_recovery_message(
            payment,
            message,
        )

        if delivery["success"]:
            log_outcome(
                db,
                payment.id,
                MESSAGE_SENT,
                (
                    "Recovery message dispatched "
                    "successfully."
                ),
            )
        else:
            log_action(
                db,
                payment.id,
                API_ERROR,
                (
                    "Recovery action completed but message "
                    "delivery failed: "
                    f"{delivery['error']}"
                ),
            )

        db.commit()

        return {
            "success": True,
            "action": action,
            "attempts": payment.attempts,
            "provider": provider_result,
            "message": message,
            "message_sent": delivery["success"],
            "message_error": delivery.get(
                "error"
            ),
            "llm_fallback_used": fallback_used,
            "status": payment.status,
        }

    except RazorpayConnectorError as exc:
        db.rollback()

        # Re-open so the exception itself can be audited.
        payment = db.get(
            FailedPayment,
            payment_id,
        )

        if payment:
            log_action(
                db,
                payment.id,
                API_ERROR,
                (
                    f"Razorpay recovery execution failed: "
                    f"{exc}"
                ),
            )

            if payment.attempts >= MAX_ATTEMPTS:
                payment.status = "abandoned"

                log_action(
                    db,
                    payment.id,
                    ABANDONED,
                    (
                        "Provider failure occurred at the "
                        "maximum allowed recovery attempt."
                    ),
                )

            db.commit()

        return {
            "success": False,
            "error": str(exc),
            "provider_error": True,
        }

    except Exception as exc:
        db.rollback()

        payment = db.get(
            FailedPayment,
            payment_id,
        )

        if payment:
            log_action(
                db,
                payment.id,
                API_ERROR,
                (
                    f"Recovery execution failed: "
                    f"{exc}"
                ),
            )

            db.commit()

        return {
            "success": False,
            "error": str(exc),
        }

    finally:
        db.close()


@app.post(
    "/payments/{payment_id}/action"
)
def payment_action(
    payment_id: int,
):
    result = execute_payment_action(
        payment_id
    )

    if (
        not result.get("success")
        and not result.get("blocked")
        and result.get("error")
        == "Payment not found."
    ):
        raise HTTPException(
            status_code=404,
            detail="Payment not found.",
        )

    return result


# ============================================================
# MANUAL RECOVERY CONFIRMATION
# ============================================================

@app.post(
    "/payments/{payment_id}/recover"
)
def mark_recovered(
    payment_id: int,
):
    db = SessionLocal()

    try:
        payment = db.get(
            FailedPayment,
            payment_id,
        )

        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Payment not found.",
            )

        if payment.status == "recovered":
            return {
                "success": True,
                "already_recovered": True,
            }

        payment.status = "recovered"
        payment.recovered_at = _utc_now()
        payment.updated_at = _utc_now()

        log_outcome(
            db,
            payment.id,
            PAYMENT_RECOVERED,
            (
                "Recovery manually confirmed from "
                "the dashboard."
            ),
        )

        db.commit()

        return {
            "success": True,
            "payment_id": payment.id,
            "amount_recovered": payment.amount,
            "status": payment.status,
        }

    finally:
        db.close()


# ============================================================
# CUSTOMER REPLY
# ============================================================

@app.post("/webhook/reply")
def customer_reply(
    payload: CustomerReplyPayload,
):
    db = SessionLocal()

    try:
        payment = db.get(
            FailedPayment,
            payload.payment_id,
        )

        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Payment not found.",
            )

        message = (
            payload.message
            .strip()
        )

        normalized = (
            message
            .lower()
            .strip()
        )

        # ----------------------------------------------------
        # OPT OUT
        # ----------------------------------------------------

        opt_out_words = {
            "stop",
            "no",
            "unsubscribe",
            "cancel",
            "do not contact",
            "dont contact",
            "don't contact",
        }

        if normalized in opt_out_words:
            payment.opted_out = True
            payment.status = "abandoned"
            payment.updated_at = _utc_now()

            log_action(
                db,
                payment.id,
                ACTION_BLOCKED,
                (
                    "Customer opt-out received. "
                    "All future automated recovery contact "
                    "must stop."
                ),
            )

            db.commit()

            return {
                "success": True,
                "type": "opt_out",
                "message": (
                    "Customer opted out. "
                    "Recovery stopped."
                ),
            }

        # ----------------------------------------------------
        # SIMPLE PTP DETECTION
        # ----------------------------------------------------

        import re

        today = _utc_now().date()

        promised_date = None

        if (
            "tomorrow" in normalized
        ):
            promised_date = (
                today
                + timedelta(days=1)
            )

        elif (
            "today" in normalized
        ):
            promised_date = today

        else:
            match = re.search(
                r"\b(\d{1,2})[/-](\d{1,2})\b",
                normalized,
            )

            if match:
                day = int(
                    match.group(1)
                )
                month = int(
                    match.group(2)
                )

                try:
                    promised_date = datetime(
                        today.year,
                        month,
                        day,
                    ).date()

                    if promised_date < today:
                        promised_date = datetime(
                            today.year + 1,
                            month,
                            day,
                        ).date()

                except ValueError:
                    promised_date = None

        if promised_date:
            from backend.db.models import (
                PromiseToPay,
            )

            existing_ptp = (
                db.query(PromiseToPay)
                .filter(
                    PromiseToPay.payment_id
                    == payment.id
                )
                .first()
            )

            if not existing_ptp:
                ptp = PromiseToPay(
                    payment_id=payment.id,
                    promised_date=promised_date,
                    fulfilled=False,
                    follow_up_sent=False,
                )

                db.add(ptp)

            log_action(
                db,
                payment.id,
                "ptp_detected",
                (
                    f"Customer promised payment on "
                    f"{promised_date.isoformat()}."
                ),
            )

            db.commit()

            return {
                "success": True,
                "type": "promise_to_pay",
                "promised_date": (
                    promised_date.isoformat()
                ),
            }

        # ----------------------------------------------------
        # GENERAL REPLY
        # ----------------------------------------------------

        log_action(
            db,
            payment.id,
            "customer_reply_received",
            (
                f"Customer reply received: "
                f"{message[:500]}"
            ),
        )

        db.commit()

        return {
            "success": True,
            "type": "reply",
            "message": (
                "Customer reply recorded."
            ),
        }

    finally:
        db.close()


# ============================================================
# METRICS
# ============================================================

@app.get("/metrics")
def metrics():
    db = SessionLocal()

    try:
        rows = (
            db.query(FailedPayment)
            .all()
        )

        total_failed_amount = sum(
            float(
                row.amount or 0
            )
            for row in rows
        )

        total_recovered_amount = sum(
            float(
                row.amount or 0
            )
            for row in rows
            if row.status == "recovered"
        )

        total_failed_count = len(
            rows
        )

        total_recovered_count = sum(
            1
            for row in rows
            if row.status == "recovered"
        )

        recovery_rate = (
            (
                total_recovered_amount
                / total_failed_amount
            )
            * 100
            if total_failed_amount
            else 0
        )

        by_reason: dict[
            str,
            dict[str, Any],
        ] = {}

        for row in rows:
            reason = (
                row.failure_reason
                or "unknown"
            )

            if reason not in by_reason:
                by_reason[reason] = {
                    "failed": 0,
                    "recovered": 0,
                    "failed_count": 0,
                    "recovered_count": 0,
                }

            by_reason[reason][
                "failed"
            ] += float(
                row.amount or 0
            )

            by_reason[reason][
                "failed_count"
            ] += 1

            if row.status == "recovered":
                by_reason[reason][
                    "recovered"
                ] += float(
                    row.amount or 0
                )

                by_reason[reason][
                    "recovered_count"
                ] += 1

        exception_count = sum(
            1
            for row in rows
            if row.status
            in {
                "abandoned",
                "escalated",
            }
        )

        result = {
            # Current frontend names.
            "total_failed_amount": (
                total_failed_amount
            ),
            "total_recovered_amount": (
                total_recovered_amount
            ),
            "total_failed_count": (
                total_failed_count
            ),
            "total_recovered_count": (
                total_recovered_count
            ),
            "recovery_rate": round(
                recovery_rate,
                2,
            ),
            "exceptions_count": (
                exception_count
            ),
            "by_reason": by_reason,

            # Backwards-compatible names.
            "failed_amount": (
                total_failed_amount
            ),
            "recovered_amount": (
                total_recovered_amount
            ),
            "exceptions": (
                exception_count
            ),
        }

        return result

    finally:
        db.close()


# ============================================================
# EXCEPTIONS
# ============================================================

@app.get("/exceptions")
def exceptions():
    db = SessionLocal()

    try:
        rows = (
            db.query(FailedPayment)
            .filter(
                FailedPayment.status.in_(
                    [
                        "abandoned",
                        "escalated",
                    ]
                )
            )
            .order_by(
                FailedPayment.updated_at.desc()
            )
            .all()
        )

        return [
            {
                "id": row.id,
                "customer_name": (
                    row.customer_name
                ),
                "customer_contact": (
                    row.customer_contact
                ),
                "amount": row.amount,
                "reason": (
                    row.failure_reason
                ),
                "failure_reason": (
                    row.failure_reason
                ),
                "status": row.status,
                "attempts": row.attempts,
                "recovery_score": (
                    row.recovery_score
                ),
            }
            for row in rows
        ]

    finally:
        db.close()