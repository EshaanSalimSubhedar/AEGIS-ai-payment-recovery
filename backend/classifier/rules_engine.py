from typing import Any, Dict


# ==========================================
# Failure categories
# ==========================================

INSUFFICIENT_FUNDS = "insufficient_funds"
BANK_TIMEOUT = "bank_timeout"
CARD_EXPIRED = "card_expired"
ISSUER_DECLINED = "issuer_declined"
NETWORK_ERROR = "network_error"
AUTHENTICATION_FAILED = "authentication_failed"
LIMIT_EXCEEDED = "limit_exceeded"
FRAUD_REVIEW = "fraud_review"
UNKNOWN = "unknown"


# ==========================================
# Razorpay error-code mappings
# ==========================================

ERROR_CODE_MAP = {
    # Insufficient funds
    "BAD_REQUEST_ERROR": UNKNOWN,

    # Common payment failures
    "payment_failed": ISSUER_DECLINED,
    "payment_timed_out": BANK_TIMEOUT,

    # Card-related failures
    "card_expired": CARD_EXPIRED,
    "expired_card": CARD_EXPIRED,

    # Issuer / bank declines
    "issuer_declined": ISSUER_DECLINED,
    "bank_declined": ISSUER_DECLINED,
    "do_not_honor": ISSUER_DECLINED,

    # Funds
    "insufficient_funds": INSUFFICIENT_FUNDS,
    "insufficient_balance": INSUFFICIENT_FUNDS,

    # Network
    "network_error": NETWORK_ERROR,
    "gateway_timeout": BANK_TIMEOUT,

    # Authentication
    "authentication_failed": AUTHENTICATION_FAILED,

    # Limits
    "limit_exceeded": LIMIT_EXCEEDED,

    # Fraud
    "fraud": FRAUD_REVIEW,
}


# ==========================================
# Text-based matching
# ==========================================

KEYWORD_MAP = {
    INSUFFICIENT_FUNDS: [
        "insufficient",
        "insufficient funds",
        "not enough balance",
        "low balance",
    ],
    BANK_TIMEOUT: [
        "timeout",
        "timed out",
        "timedout",
        "gateway timeout",
    ],
    CARD_EXPIRED: [
        "expired",
        "expiry",
        "expiration",
    ],
    ISSUER_DECLINED: [
        "declined",
        "issuer",
        "bank decline",
        "do not honor",
    ],
    NETWORK_ERROR: [
        "network",
        "connection",
    ],
    AUTHENTICATION_FAILED: [
        "authentication",
        "authentication failed",
        "3ds failed",
    ],
    LIMIT_EXCEEDED: [
        "limit exceeded",
        "transaction limit",
    ],
    FRAUD_REVIEW: [
        "fraud",
        "risk",
        "suspicious",
    ],
}


# ==========================================
# Classifier
# ==========================================

def classify_failure(
    error_code: str | None = None,
    error_description: str | None = None,
    raw_data: Dict[str, Any] | None = None,
) -> str:
    """
    Convert raw payment failure information into a
    normalized failure category.

    Classification order:

        1. Explicit error code
        2. Error description
        3. Raw response text
        4. UNKNOWN
    """

    normalized_code = (error_code or "").strip().lower()

    # --------------------------------------
    # 1. Exact error-code matching
    # --------------------------------------

    if normalized_code in ERROR_CODE_MAP:
        return ERROR_CODE_MAP[normalized_code]

    # --------------------------------------
    # 2. Partial error-code matching
    # --------------------------------------

    for code, category in ERROR_CODE_MAP.items():
        if code.lower() in normalized_code:
            return category

    # --------------------------------------
    # 3. Description matching
    # --------------------------------------

    description = (
        error_description
        or ""
    ).strip().lower()

    if description:
        for category, keywords in KEYWORD_MAP.items():
            for keyword in keywords:
                if keyword in description:
                    return category

    # --------------------------------------
    # 4. Search raw response
    # --------------------------------------

    if raw_data:
        raw_text = str(raw_data).lower()

        for category, keywords in KEYWORD_MAP.items():
            for keyword in keywords:
                if keyword in raw_text:
                    return category

    # --------------------------------------
    # 5. Unknown
    # --------------------------------------

    return UNKNOWN


# ==========================================
# Human-readable explanation
# ==========================================

def explain_failure(
    failure_reason: str,
) -> str:
    """
    Convert an internal failure category into a
    human-readable explanation for the dashboard.
    """

    explanations = {
        INSUFFICIENT_FUNDS:
            "The customer's available balance appears insufficient.",

        BANK_TIMEOUT:
            "The payment attempt timed out while communicating with the bank or gateway.",

        CARD_EXPIRED:
            "The payment method appears to have expired.",

        ISSUER_DECLINED:
            "The card issuer or bank declined the transaction.",

        NETWORK_ERROR:
            "A network or connectivity problem interrupted the payment attempt.",

        AUTHENTICATION_FAILED:
            "Payment authentication could not be completed.",

        LIMIT_EXCEEDED:
            "The transaction appears to have exceeded a payment or bank limit.",

        FRAUD_REVIEW:
            "The transaction requires additional risk or fraud review.",

        UNKNOWN:
            "The payment failure could not be confidently categorized.",
    }

    return explanations.get(
        failure_reason,
        explanations[UNKNOWN],
    )