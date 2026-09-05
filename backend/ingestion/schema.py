from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FailedPaymentInput(BaseModel):
    """
    Normalized representation of a failed payment.

    This is the format used internally by the recovery agent,
    regardless of the shape of the original Razorpay response.
    """

    razorpay_payment_id: str = Field(
        ...,
        description="Razorpay payment identifier",
    )

    customer_name: str = Field(
        default="Customer",
        description="Customer display name",
    )

    customer_contact: str = Field(
        ...,
        description="Phone number or email used for recovery messaging",
    )

    amount: float = Field(
        ...,
        gt=0,
        description="Payment amount in INR",
    )

    error_code: Optional[str] = Field(
        default=None,
        description="Raw Razorpay error code",
    )

    error_description: Optional[str] = Field(
        default=None,
        description="Raw Razorpay error description",
    )

    language_pref: str = Field(
        default="english",
        description="Preferred customer language",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Time at which the payment failure occurred",
    )

    raw_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Original provider response for debugging/audit purposes",
    )


class PaymentWebhookPayload(BaseModel):
    """
    Minimal structure for incoming webhook data.

    Razorpay can send additional fields, so the connector
    is responsible for extracting the fields required by
    FailedPaymentInput.
    """

    event: str

    payload: dict[str, Any]


def normalize_amount(
    amount: Any,
) -> float:
    """
    Convert an amount received from Razorpay into INR.

    Razorpay commonly represents payment amounts in the
    smallest currency unit, such as paise.

    Example:

        150000 -> ₹1500.00
    """

    if amount is None:
        raise ValueError("Payment amount is missing.")

    numeric_amount = float(amount)

    # Razorpay payment/order amounts are normally supplied
    # in paise. Convert to rupees for our internal model.
    return round(numeric_amount / 100, 2)


def normalize_razorpay_payment(
    data: dict[str, Any],
) -> FailedPaymentInput:
    """
    Convert a raw Razorpay payment response into the
    internal FailedPaymentInput schema.

    The function deliberately keeps the original response
    in raw_data so the agent can remain explainable and
    debuggable.
    """

    payment_id = data.get("id")

    if not payment_id:
        raise ValueError(
            "Razorpay payment ID is missing."
        )

    amount = data.get("amount")

    if amount is None:
        raise ValueError(
            f"Payment {payment_id} has no amount."
        )

    # Razorpay payment responses may contain:
    #
    #   email
    #   contact
    #
    # We use whichever contact field is available.
    contact = (
        data.get("contact")
        or data.get("email")
    )

    if not contact:
        raise ValueError(
            f"Payment {payment_id} has no customer contact."
        )

    error_code = (
        data.get("error_code")
        or data.get("error", {}).get("code")
    )

    error_description = (
        data.get("error_description")
        or data.get("error", {}).get("description")
    )

    created_timestamp = data.get("created_at")

    if created_timestamp:
        created_at = datetime.fromtimestamp(
            created_timestamp
        )
    else:
        created_at = datetime.utcnow()

    return FailedPaymentInput(
        razorpay_payment_id=str(payment_id),
        customer_name=(
            data.get("customer_name")
            or data.get("name")
            or "Customer"
        ),
        customer_contact=str(contact),
        amount=normalize_amount(amount),
        error_code=error_code,
        error_description=error_description,
        language_pref=(
            data.get("language_pref")
            or "english"
        ),
        created_at=created_at,
        raw_data=data,
    )