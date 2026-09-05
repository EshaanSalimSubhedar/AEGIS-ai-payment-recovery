import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.db.models import (
    Base,
    FailedPayment,
    SessionLocal,
    engine,
)


# ============================================================
# TEST DATABASE CLEANUP
# ============================================================

@pytest.fixture(autouse=True)
def clean_database():
    """
    Clean the SQLite database before and after every test.

    The MVP uses SQLite, so this keeps API tests isolated.
    """

    Base.metadata.drop_all(
        bind=engine
    )

    Base.metadata.create_all(
        bind=engine
    )

    yield

    Base.metadata.drop_all(
        bind=engine
    )

    Base.metadata.create_all(
        bind=engine
    )


@pytest.fixture
def client():
    """
    FastAPI test client.
    """

    return TestClient(app)


# ============================================================
# HEALTH TESTS
# ============================================================

def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == (
        "AI Failed-Payment Recovery Agent"
    )

    assert data["status"] == "running"


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert "timestamp" in data


# ============================================================
# INGESTION TESTS
# ============================================================

def test_ingest_failed_payment(client):
    payload = {
        "razorpay_payment_id": "pay_test_api_001",
        "customer_name": "Alex",
        "customer_contact": "+919999999999",
        "amount": 1500,
        "error_code": "insufficient_funds",
        "error_description": "Insufficient balance",
        "language_pref": "english",
    }

    response = client.post(
        "/ingest",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True

    payment = data["payment"]

    assert payment["razorpay_payment_id"] == (
        "pay_test_api_001"
    )

    assert payment["customer_name"] == "Alex"

    assert payment["amount"] == 1500

    assert payment["failure_reason"] == (
        "insufficient_funds"
    )

    assert payment["attempts"] == 0

    assert payment["status"] == "retrying"


def test_ingest_creates_audit_trail(client):
    payload = {
        "razorpay_payment_id": "pay_test_api_002",
        "customer_name": "Priya",
        "customer_contact": "+919888888888",
        "amount": 2500,
        "error_code": "card_expired",
        "error_description": "Card has expired",
        "language_pref": "english",
    }

    response = client.post(
        "/ingest",
        json=payload,
    )

    assert response.status_code == 200

    payment_id = (
        response.json()["payment"]["id"]
    )

    audit_response = client.get(
        f"/payments/{payment_id}/audit"
    )

    assert audit_response.status_code == 200

    audit = audit_response.json()

    assert len(audit) >= 4

    actions = [
        entry["action"]
        for entry in audit
    ]

    assert "payment_ingested" in actions
    assert "failure_classified" in actions
    assert "recovery_scored" in actions
    assert "action_planned" in actions


# ============================================================
# DUPLICATE INGESTION
# ============================================================

def test_duplicate_payment_is_not_created(client):
    payload = {
        "razorpay_payment_id": "pay_duplicate_001",
        "customer_name": "Alex",
        "customer_contact": "+919999999999",
        "amount": 1000,
        "error_code": "bank_declined",
        "language_pref": "english",
    }

    first_response = client.post(
        "/ingest",
        json=payload,
    )

    second_response = client.post(
        "/ingest",
        json=payload,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_id = (
        first_response.json()["payment"]["id"]
    )

    second_id = (
        second_response.json()["payment"]["id"]
    )

    assert first_id == second_id

    payments_response = client.get(
        "/payments"
    )

    assert payments_response.status_code == 200

    payments = payments_response.json()

    assert len(payments) == 1


# ============================================================
# PAYMENT RETRIEVAL
# ============================================================

def test_get_payment(client):
    payload = {
        "razorpay_payment_id": "pay_get_001",
        "customer_name": "Sam",
        "customer_contact": "+919777777777",
        "amount": 500,
        "error_code": "payment_timed_out",
        "language_pref": "english",
    }

    create_response = client.post(
        "/ingest",
        json=payload,
    )

    payment_id = (
        create_response
        .json()["payment"]["id"]
    )

    response = client.get(
        f"/payments/{payment_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == payment_id
    assert data["amount"] == 500
    assert data["failure_reason"] == (
        "bank_timeout"
    )


def test_get_missing_payment_returns_404(client):
    response = client.get(
        "/payments/999999"
    )

    assert response.status_code == 404


# ============================================================
# EXCEPTIONS
# ============================================================

def test_exceptions_endpoint(client):
    payload = {
        "razorpay_payment_id": "pay_exception_001",
        "customer_name": "Test User",
        "customer_contact": "+919666666666",
        "amount": 3000,
        "error_code": "issuer_declined",
        "language_pref": "english",
    }

    response = client.post(
        "/ingest",
        json=payload,
    )

    assert response.status_code == 200

    exceptions_response = client.get(
        "/exceptions"
    )

    assert exceptions_response.status_code == 200

    exceptions = exceptions_response.json()

    # Low-score issuer declines should normally
    # be escalated by the action planner.
    assert len(exceptions) >= 1

    assert any(
        item["razorpay_payment_id"]
        == "pay_exception_001"
        for item in exceptions
    )


# ============================================================
# METRICS
# ============================================================

def test_metrics_endpoint(client):
    first_payload = {
        "razorpay_payment_id": "pay_metric_001",
        "customer_name": "Alex",
        "customer_contact": "+919555555555",
        "amount": 1000,
        "error_code": "insufficient_funds",
    }

    second_payload = {
        "razorpay_payment_id": "pay_metric_002",
        "customer_name": "Sam",
        "customer_contact": "+919444444444",
        "amount": 2000,
        "error_code": "card_expired",
    }

    client.post(
        "/ingest",
        json=first_payload,
    )

    client.post(
        "/ingest",
        json=second_payload,
    )

    response = client.get(
        "/metrics"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_failed_amount"] == 3000
    assert data["total_failed_payments"] == 2

    assert "total_recovered_amount" in data
    assert "recovery_rate" in data
    assert "exceptions_count" in data
    assert "by_failure_reason" in data


# ============================================================
# MANUAL RECOVERY DEMO
# ============================================================

def test_mark_payment_recovered(client):
    payload = {
        "razorpay_payment_id": "pay_recover_001",
        "customer_name": "Recovery Test",
        "customer_contact": "+919333333333",
        "amount": 1250,
        "error_code": "payment_timed_out",
    }

    create_response = client.post(
        "/ingest",
        json=payload,
    )

    payment_id = (
        create_response
        .json()["payment"]["id"]
    )

    response = client.post(
        f"/payments/{payment_id}/recover"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["payment"]["status"] == (
        "recovered"
    )

    metrics_response = client.get(
        "/metrics"
    )

    metrics = metrics_response.json()

    assert metrics[
        "total_recovered_amount"
    ] == 1250

    assert metrics[
        "total_recovered_payments"
    ] == 1

    assert metrics[
        "recovery_rate"
    ] == 100


# ============================================================
# CUSTOMER OPT-OUT
# ============================================================

def test_customer_stop_blocks_recovery(client):
    payload = {
        "razorpay_payment_id": "pay_stop_001",
        "customer_name": "Opt Out User",
        "customer_contact": "+919222222222",
        "amount": 800,
        "error_code": "payment_timed_out",
    }

    create_response = client.post(
        "/ingest",
        json=payload,
    )

    payment_id = (
        create_response
        .json()["payment"]["id"]
    )

    response = client.post(
        "/webhook/reply",
        json={
            "payment_id": payment_id,
            "message": "STOP",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["type"] == "opt_out"
    assert data["status"] == "abandoned"

    payment_response = client.get(
        f"/payments/{payment_id}"
    )

    payment = payment_response.json()

    assert payment["opted_out"] is True
    assert payment["status"] == "abandoned"


# ============================================================
# PROMISE TO PAY API
# ============================================================

def test_customer_ptp_creates_promise(client):
    payload = {
        "razorpay_payment_id": "pay_ptp_api_001",
        "customer_name": "PTP User",
        "customer_contact": "+919111111111",
        "amount": 2000,
        "error_code": "insufficient_funds",
    }

    create_response = client.post(
        "/ingest",
        json=payload,
    )

    payment_id = (
        create_response
        .json()["payment"]["id"]
    )

    response = client.post(
        "/webhook/reply",
        json={
            "payment_id": payment_id,
            "message": "I'll pay on September 10",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["type"] == (
        "promise_to_pay"
    )

    assert data["promised_date"].startswith(
        "2026-09-10"
    )


# ============================================================
# INVALID ACTION
# ============================================================

def test_invalid_action_returns_400(client):
    payload = {
        "razorpay_payment_id": "pay_action_001",
        "customer_name": "Action Test",
        "customer_contact": "+919000000000",
        "amount": 1000,
        "error_code": "card_expired",
    }

    create_response = client.post(
        "/ingest",
        json=payload,
    )

    payment_id = (
        create_response
        .json()["payment"]["id"]
    )

    response = client.post(
        f"/payments/{payment_id}/action",
        json={
            "action": "definitely_invalid_action",
        },
    )

    assert response.status_code == 400


# ============================================================
# RECOVERED PAYMENT SAFETY
# ============================================================

def test_recovered_payment_cannot_be_retried(client):
    payload = {
        "razorpay_payment_id": "pay_safety_001",
        "customer_name": "Safety Test",
        "customer_contact": "+918999999999",
        "amount": 1000,
        "error_code": "payment_timed_out",
    }

    create_response = client.post(
        "/ingest",
        json=payload,
    )

    payment_id = (
        create_response
        .json()["payment"]["id"]
    )

    client.post(
        f"/payments/{payment_id}/recover"
    )

    response = client.post(
        f"/payments/{payment_id}/action",
        json={
            "action": "immediate_retry",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is False
    assert data["blocked"] is True
    assert data["reason"] == (
        "payment_recovered"
    )


# ============================================================
# MAXIMUM RETRY SAFETY
# ============================================================

def test_maximum_retry_limit_blocks_action(client):
    payload = {
        "razorpay_payment_id": "pay_max_retry_001",
        "customer_name": "Retry Test",
        "customer_contact": "+918888888888",
        "amount": 1000,
        "error_code": "payment_timed_out",
    }

    create_response = client.post(
        "/ingest",
        json=payload,
    )

    payment_id = (
        create_response
        .json()["payment"]["id"]
    )

    db = SessionLocal()

    try:
        payment = (
            db.query(FailedPayment)
            .filter(
                FailedPayment.id
                == payment_id
            )
            .first()
        )

        payment.attempts = 3
        payment.status = "retrying"

        db.commit()

    finally:
        db.close()

    response = client.post(
        f"/payments/{payment_id}/action",
        json={
            "action": "immediate_retry",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is False
    assert data["blocked"] is True
    assert data["reason"] == (
        "max_attempts_reached"
    )

    assert data["payment"]["status"] == (
        "abandoned"
    )