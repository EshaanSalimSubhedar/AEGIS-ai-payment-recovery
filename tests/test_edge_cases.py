from datetime import date, datetime, timedelta

import pytest

from backend.classifier.risk_scorer import (
    calculate_recovery_score,
    score_category,
)

from backend.classifier.rules_engine import (
    BANK_TIMEOUT,
    CARD_EXPIRED,
    INSUFFICIENT_FUNDS,
    ISSUER_DECLINED,
    UNKNOWN,
    classify_failure,
)

from backend.ingestion.schema import (
    FailedPaymentInput,
    normalize_razorpay_payment,
)

from backend.messaging.llm_composer import (
    LLMComposer,
    build_fallback_message,
)

from backend.strategy.action_planner import (
    ABANDON,
    DELAYED_RETRY,
    HUMAN_REVIEW,
    IMMEDIATE_RETRY,
    PAYMENT_LINK,
    plan_action,
)

from backend.tracker.promise_tracker import (
    detect_promise_to_pay,
    parse_promised_date,
    ptp_follow_up_datetime,
)

from backend.tracker.stopping_rules import (
    can_execute_automated_action,
    cooldown_active,
    max_attempts_reached,
)


# ============================================================
# FAILURE CLASSIFICATION TESTS
# ============================================================

def test_classifies_insufficient_funds():
    result = classify_failure(
        error_code="insufficient_funds",
    )

    assert result == INSUFFICIENT_FUNDS


def test_classifies_timeout_from_description():
    result = classify_failure(
        error_description=(
            "The bank request timed out."
        ),
    )

    assert result == BANK_TIMEOUT


def test_classifies_expired_card():
    result = classify_failure(
        error_code="card_expired",
    )

    assert result == CARD_EXPIRED


def test_classifies_issuer_decline():
    result = classify_failure(
        error_code="issuer_declined",
    )

    assert result == ISSUER_DECLINED


def test_unknown_failure_is_safe():
    result = classify_failure(
        error_code="completely_unknown_error",
        error_description="Something went wrong.",
    )

    assert result == UNKNOWN


# ============================================================
# RISK SCORING TESTS
# ============================================================

def test_recovery_score_is_between_zero_and_one():
    score = calculate_recovery_score(
        amount=1000,
        failure_reason=BANK_TIMEOUT,
        created_at=datetime.utcnow(),
    )

    assert 0.0 <= score <= 1.0


def test_high_recovery_case_gets_high_score():
    score = calculate_recovery_score(
        amount=500,
        failure_reason=BANK_TIMEOUT,
        created_at=datetime.utcnow(),
    )

    assert score >= 0.70
    assert score_category(score) == "high"


def test_expired_card_has_lower_score():
    score = calculate_recovery_score(
        amount=5000,
        failure_reason=CARD_EXPIRED,
        created_at=datetime.utcnow(),
    )

    assert score < 0.70


def test_large_payment_is_penalized():
    small_payment_score = calculate_recovery_score(
        amount=500,
        failure_reason=BANK_TIMEOUT,
        created_at=datetime.utcnow(),
    )

    large_payment_score = calculate_recovery_score(
        amount=100000,
        failure_reason=BANK_TIMEOUT,
        created_at=datetime.utcnow(),
    )

    assert large_payment_score < small_payment_score


# ============================================================
# ACTION PLANNER TESTS
# ============================================================

def test_bank_timeout_high_score_gets_immediate_retry():
    decision = plan_action(
        failure_reason=BANK_TIMEOUT,
        recovery_score=0.90,
        attempts=0,
    )

    assert decision.action == IMMEDIATE_RETRY


def test_insufficient_funds_gets_delayed_retry():
    decision = plan_action(
        failure_reason=INSUFFICIENT_FUNDS,
        recovery_score=0.70,
        attempts=0,
    )

    assert decision.action == DELAYED_RETRY
    assert decision.delay_hours == 24


def test_expired_card_gets_payment_link():
    decision = plan_action(
        failure_reason=CARD_EXPIRED,
        recovery_score=0.30,
        attempts=0,
    )

    assert decision.action == PAYMENT_LINK


def test_low_probability_issuer_decline_goes_to_human():
    decision = plan_action(
        failure_reason=ISSUER_DECLINED,
        recovery_score=0.20,
        attempts=0,
    )

    assert decision.action == HUMAN_REVIEW


def test_max_attempts_results_in_abandon():
    decision = plan_action(
        failure_reason=BANK_TIMEOUT,
        recovery_score=0.90,
        attempts=3,
        max_attempts=3,
    )

    assert decision.action == ABANDON


def test_opted_out_customer_is_abandoned():
    decision = plan_action(
        failure_reason=BANK_TIMEOUT,
        recovery_score=0.95,
        attempts=0,
        opted_out=True,
    )

    assert decision.action == ABANDON


# ============================================================
# STOPPING RULE TESTS
# ============================================================

def test_max_attempts_detected():
    assert max_attempts_reached(
        attempts=3,
        max_attempts=3,
    )


def test_attempts_below_limit_are_allowed():
    assert not max_attempts_reached(
        attempts=2,
        max_attempts=3,
    )


def test_cooldown_is_active():
    last_attempt = datetime.utcnow()

    assert cooldown_active(
        last_attempt_at=last_attempt,
        cooldown_hours=2,
    )


def test_cooldown_is_not_active_after_two_hours():
    last_attempt = (
        datetime.utcnow()
        - timedelta(hours=3)
    )

    assert not cooldown_active(
        last_attempt_at=last_attempt,
        cooldown_hours=2,
    )


def test_opt_out_blocks_action():
    allowed, reason = (
        can_execute_automated_action(
            attempts=0,
            max_attempts=3,
            last_attempt_at=None,
            opted_out=True,
            status="retrying",
            cooldown_hours=2,
        )
    )

    assert not allowed
    assert reason == "opted_out"


def test_max_attempts_blocks_action():
    allowed, reason = (
        can_execute_automated_action(
            attempts=3,
            max_attempts=3,
            last_attempt_at=None,
            opted_out=False,
            status="retrying",
            cooldown_hours=2,
        )
    )

    assert not allowed
    assert reason == "max_attempts_reached"


def test_recovered_payment_cannot_be_retried():
    allowed, reason = (
        can_execute_automated_action(
            attempts=0,
            max_attempts=3,
            last_attempt_at=None,
            opted_out=False,
            status="recovered",
            cooldown_hours=2,
        )
    )

    assert not allowed
    assert reason == "payment_recovered"


def test_active_payment_can_execute():
    allowed, reason = (
        can_execute_automated_action(
            attempts=0,
            max_attempts=3,
            last_attempt_at=None,
            opted_out=False,
            status="retrying",
            cooldown_hours=2,
        )
    )

    assert allowed
    assert reason == "active"


# ============================================================
# LLM FALLBACK TESTS
# ============================================================

def test_static_fallback_message_is_generated():
    message = build_fallback_message(
        customer_name="Alex",
        amount=1500,
        failure_reason=BANK_TIMEOUT,
    )

    assert "Alex" in message
    assert "1500" in message
    assert len(message) <= 480


def test_llm_without_api_key_uses_fallback():
    composer = LLMComposer(
        api_key=None,
    )

    message, fallback_used = composer.compose(
        customer_name="Alex",
        amount=1500,
        failure_reason=BANK_TIMEOUT,
        action=IMMEDIATE_RETRY,
    )

    assert message
    assert fallback_used is True


def test_llm_fallback_does_not_crash():
    composer = LLMComposer(
        api_key=None,
    )

    message, fallback_used = composer.compose(
        customer_name="Priya",
        amount=2500,
        failure_reason=INSUFFICIENT_FUNDS,
        action=DELAYED_RETRY,
    )

    assert isinstance(message, str)
    assert len(message) > 0
    assert fallback_used


# ============================================================
# RAZORPAY NORMALIZATION TESTS
# ============================================================

def test_normalizes_razorpay_amount_from_paise():
    raw_payment = {
        "id": "pay_test_001",
        "amount": 150000,
        "contact": "+919999999999",
        "name": "Alex",
        "error_code": "insufficient_funds",
        "error_description": "Insufficient balance",
    }

    result = normalize_razorpay_payment(
        raw_payment
    )

    assert result.razorpay_payment_id == "pay_test_001"
    assert result.amount == 1500.00
    assert result.customer_name == "Alex"
    assert result.customer_contact == "+919999999999"


def test_malformed_razorpay_payment_without_id_fails():
    raw_payment = {
        "amount": 150000,
        "contact": "+919999999999",
    }

    with pytest.raises(ValueError):
        normalize_razorpay_payment(
            raw_payment
        )


def test_malformed_razorpay_payment_without_contact_fails():
    raw_payment = {
        "id": "pay_test_002",
        "amount": 150000,
    }

    with pytest.raises(ValueError):
        normalize_razorpay_payment(
            raw_payment
        )


# ============================================================
# PTP TESTS
# ============================================================

def test_detects_numeric_ptp_date():
    reference = date(
        2026,
        9,
        4,
    )

    promised = parse_promised_date(
        "I'll pay on 10/09",
        reference_date=reference,
    )

    assert promised == date(
        2026,
        9,
        10,
    )


def test_detects_named_ptp_date():
    reference = date(
        2026,
        9,
        4,
    )

    promised = detect_promise_to_pay(
        "I'll pay on September 10",
        reference_date=reference,
    )

    assert promised == date(
        2026,
        9,
        10,
    )

def test_detects_ptp_with_by():
    reference = date(
        2026,
        9,
        4,
    )

    promised = detect_promise_to_pay(
        "I'll pay by September 10",
        reference_date=reference,
    )

    assert promised == date(
        2026,
        9,
        10,
    )


def test_detects_ptp_without_on():
    reference = date(
        2026,
        9,
        4,
    )

    promised = detect_promise_to_pay(
        "I will pay September 10",
        reference_date=reference,
    )

    assert promised == date(
        2026,
        9,
        10,
    )

def test_detects_tomorrow():
    reference = date(
        2026,
        9,
        4,
    )

    promised = detect_promise_to_pay(
        "I will pay tomorrow",
        reference_date=reference,
    )

    assert promised == date(
        2026,
        9,
        5,
    )


def test_non_ptp_message_returns_none():
    result = detect_promise_to_pay(
        "I am having trouble with my card."
    )

    assert result is None


def test_ptp_follow_up_is_on_promised_date():
    promised_date = date(
        2026,
        9,
        10,
    )

    follow_up = ptp_follow_up_datetime(
        promised_date
    )

    assert follow_up.date() == promised_date
    assert follow_up.hour == 9


# ============================================================
# TEST SUMMARY
# ============================================================

def test_core_safety_requirements_exist():
    """
    Meta-test documenting the minimum safety guarantees
    expected by the hackathon MVP.
    """

    # Maximum three attempts
    assert max_attempts_reached(
        3,
        3,
    )

    # Opt-out blocks recovery
    allowed, _ = can_execute_automated_action(
        attempts=0,
        max_attempts=3,
        last_attempt_at=None,
        opted_out=True,
        status="retrying",
        cooldown_hours=2,
    )

    assert not allowed

    # LLM fallback works without credentials
    composer = LLMComposer(
        api_key=None,
    )

    message, fallback = composer.compose(
        customer_name="Test",
        amount=100,
        failure_reason=UNKNOWN,
        action=HUMAN_REVIEW,
    )

    assert message
    assert fallback