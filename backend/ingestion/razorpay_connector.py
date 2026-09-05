from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import razorpay


class RazorpayConnectorError(Exception):
    """Raised when a Razorpay operation cannot be completed."""


@dataclass
class PaymentLinkResult:
    link_id: str
    short_url: str


@dataclass
class RecoveryOrderResult:
    order_id: str
    amount: float
    currency: str
    status: str
    demo_mode: bool = False


class RazorpayConnector:
    """
    Thin wrapper around the Razorpay API.

    Responsibilities:
    - Fetch payments
    - Fetch failed payments
    - Create Payment Links
    - Create recovery Orders
    - Apply bounded API retries
    - Provide a deterministic demo mode

    Important:
    Razorpay does not expose a generic "retry this failed payment"
    operation. A recovery retry therefore creates a fresh payment
    collection flow instead of attempting to mutate/re-charge the
    original failed payment.
    """

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        demo_mode: Optional[bool] = None,
        max_attempts: Optional[int] = None,
        initial_delay_seconds: Optional[float] = None,
        backoff_multiplier: Optional[float] = None,
    ) -> None:
        self.key_id = key_id or os.getenv("RAZORPAY_KEY_ID")
        self.key_secret = key_secret or os.getenv("RAZORPAY_KEY_SECRET")

        if demo_mode is None:
            demo_mode = (
                os.getenv(
                    "RAZORPAY_DEMO_MODE",
                    "false",
                ).lower()
                in {"1", "true", "yes", "on"}
            )

        self.demo_mode = demo_mode

        self.max_attempts = int(
            max_attempts
            if max_attempts is not None
            else os.getenv(
                "RAZORPAY_API_MAX_ATTEMPTS",
                "2",
            )
        )

        self.initial_delay_seconds = float(
            initial_delay_seconds
            if initial_delay_seconds is not None
            else os.getenv(
                "RAZORPAY_API_INITIAL_DELAY_SECONDS",
                "1",
            )
        )

        self.backoff_multiplier = float(
            backoff_multiplier
            if backoff_multiplier is not None
            else os.getenv(
                "RAZORPAY_API_BACKOFF_MULTIPLIER",
                "2",
            )
        )

        if not self.demo_mode and (
            not self.key_id or not self.key_secret
        ):
            raise RazorpayConnectorError(
                "Razorpay credentials are missing. "
                "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET, "
                "or enable RAZORPAY_DEMO_MODE=true."
            )

        self.client = None

        if not self.demo_mode:
            try:
                self.client = razorpay.Client(
                    auth=(
                        self.key_id,
                        self.key_secret,
                    )
                )
            except Exception as exc:
                raise RazorpayConnectorError(
                    f"Unable to initialize Razorpay client: {exc}"
                ) from exc

    # ============================================================
    # INTERNAL RETRY WRAPPER
    # ============================================================

    def _execute_with_retry(
        self,
        operation: Callable[[], Any],
        operation_name: str,
    ) -> Any:
        """
        Execute a provider operation with bounded exponential backoff.

        The configured max attempts defaults to 2, as required by the
        recovery-agent graceful-failure design.
        """

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return operation()

            except Exception as exc:
                last_error = exc

                if attempt >= self.max_attempts:
                    break

                delay = (
                    self.initial_delay_seconds
                    * (
                        self.backoff_multiplier
                        ** (attempt - 1)
                    )
                )

                time.sleep(delay)

        raise RazorpayConnectorError(
            f"Razorpay operation '{operation_name}' failed "
            f"after {self.max_attempts} attempts: "
            f"{last_error}"
        ) from last_error

    # ============================================================
    # FETCH PAYMENT
    # ============================================================

    def fetch_payment(
        self,
        payment_id: str,
    ) -> Dict[str, Any]:
        if not payment_id:
            raise RazorpayConnectorError(
                "payment_id is required."
            )

        if self.demo_mode:
            return {
                "id": payment_id,
                "status": "failed",
                "amount": 0,
                "currency": "INR",
                "method": "card",
                "error_code": "demo_error",
                "error_description": (
                    "Demo-mode payment"
                ),
            }

        return self._execute_with_retry(
            lambda: self.client.payment.fetch(
                payment_id
            ),
            "fetch_payment",
        )

    # ============================================================
    # FAILED PAYMENT
    # ============================================================

    def get_failed_payment(
        self,
        payment_id: str,
    ) -> Dict[str, Any]:
        payment = self.fetch_payment(
            payment_id
        )

        status = str(
            payment.get("status", "")
        ).lower()

        if status != "failed":
            raise RazorpayConnectorError(
                f"Payment {payment_id} is not failed "
                f"(status={status})."
            )

        return payment

    # ============================================================
    # CREATE PAYMENT LINK
    # ============================================================

    def create_payment_link(
        self,
        amount: float,
        customer_name: str,
        customer_contact: str,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
        currency: str = "INR",
    ) -> PaymentLinkResult:
        """
        Create a Razorpay Payment Link.

        Amount supplied internally is in INR, while Razorpay expects
        the smallest currency unit (paise for INR).
        """

        if amount <= 0:
            raise RazorpayConnectorError(
                "Payment-link amount must be greater than zero."
            )

        if not customer_name:
            customer_name = "Customer"

        if not customer_contact:
            raise RazorpayConnectorError(
                "Customer contact is required."
            )

        reference_id = (
            reference_id
            or f"recovery_{uuid.uuid4().hex[:16]}"
        )

        # Razorpay reference IDs have a maximum length.
        reference_id = reference_id[:40]

        description = (
            description
            or "Payment recovery"
        )

        amount_in_subunits = int(
            round(amount * 100)
        )

        # --------------------------------------------------------
        # DEMO MODE
        # --------------------------------------------------------

        if self.demo_mode:
            link_id = (
                f"plink_demo_{uuid.uuid4().hex[:12]}"
            )

            short_url = (
                "http://localhost:5173/"
                f"recover/{link_id}"
            )

            return PaymentLinkResult(
                link_id=link_id,
                short_url=short_url,
            )

        # --------------------------------------------------------
        # LIVE / TEST RAZORPAY
        # --------------------------------------------------------

        payload: Dict[str, Any] = {
            "amount": amount_in_subunits,
            "currency": currency,
            "accept_partial": False,
            "reference_id": reference_id,
            "description": description,
            "customer": {
                "name": customer_name,
                "contact": customer_contact,
            },
            "reminder_enable": True,
            "notes": {
                "recovery_reference": reference_id,
                "recovery_agent": (
                    "ai-failed-payment-recovery"
                ),
            },
        }

        response = self._execute_with_retry(
            lambda: self.client.payment_link.create(
                payload
            ),
            "create_payment_link",
        )

        link_id = response.get("id")
        short_url = response.get("short_url")

        if not link_id or not short_url:
            raise RazorpayConnectorError(
                "Razorpay returned an invalid Payment Link response."
            )

        return PaymentLinkResult(
            link_id=link_id,
            short_url=short_url,
        )

    # ============================================================
    # CREATE RECOVERY ORDER
    # ============================================================

    def create_recovery_order(
        self,
        amount: float,
        reference_id: Optional[str] = None,
        currency: str = "INR",
        notes: Optional[Dict[str, str]] = None,
    ) -> RecoveryOrderResult:
        """
        Create a fresh Razorpay Order for a retry-style recovery.

        This intentionally does NOT attempt to charge the original
        failed payment again.

        The resulting order can be used by a Checkout integration
        to collect the payment from the customer.
        """

        if amount <= 0:
            raise RazorpayConnectorError(
                "Recovery order amount must be greater than zero."
            )

        reference_id = (
            reference_id
            or f"recovery_{uuid.uuid4().hex[:16]}"
        )

        reference_id = reference_id[:40]

        amount_in_subunits = int(
            round(amount * 100)
        )

        order_notes = {
            "recovery_reference": reference_id,
            "recovery_agent": (
                "ai-failed-payment-recovery"
            ),
        }

        if notes:
            order_notes.update(
                {
                    str(key): str(value)
                    for key, value in notes.items()
                }
            )

        # --------------------------------------------------------
        # DEMO MODE
        # --------------------------------------------------------

        if self.demo_mode:
            return RecoveryOrderResult(
                order_id=(
                    f"order_demo_"
                    f"{uuid.uuid4().hex[:12]}"
                ),
                amount=amount,
                currency=currency,
                status="created",
                demo_mode=True,
            )

        # --------------------------------------------------------
        # LIVE / TEST RAZORPAY
        # --------------------------------------------------------

        payload = {
            "amount": amount_in_subunits,
            "currency": currency,
            "receipt": reference_id,
            "notes": order_notes,
        }

        response = self._execute_with_retry(
            lambda: self.client.order.create(
                payload
            ),
            "create_recovery_order",
        )

        order_id = response.get("id")

        if not order_id:
            raise RazorpayConnectorError(
                "Razorpay returned an invalid Order response."
            )

        response_amount = response.get(
            "amount",
            amount_in_subunits,
        )

        return RecoveryOrderResult(
            order_id=order_id,
            amount=(
                float(response_amount) / 100
            ),
            currency=response.get(
                "currency",
                currency,
            ),
            status=response.get(
                "status",
                "created",
            ),
            demo_mode=False,
        )

    # ============================================================
    # FETCH FAILED PAYMENTS
    # ============================================================

    def fetch_failed_payments(
        self,
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent failed payments.

        Demo mode intentionally returns an empty list here. Demo
        payments should enter the system through /ingest so the
        ingestion pipeline remains identical to real data.
        """

        count = max(
            1,
            min(int(count), 100),
        )

        if self.demo_mode:
            return []

        def fetch() -> Any:
            return self.client.payment.all(
                {
                    "count": count,
                }
            )

        response = self._execute_with_retry(
            fetch,
            "fetch_payments",
        )

        if isinstance(response, dict):
            items = response.get(
                "items",
                [],
            )
        else:
            items = response

        if not isinstance(items, list):
            return []

        failed = []

        for payment in items:
            if not isinstance(payment, dict):
                continue

            status = str(
                payment.get(
                    "status",
                    "",
                )
            ).lower()

            if status == "failed":
                failed.append(payment)

        return failed

    # ============================================================
    # NORMALIZATION HELPER
    # ============================================================

    @staticmethod
    def amount_from_razorpay(
        amount_in_subunits: Any,
    ) -> float:
        """
        Convert Razorpay smallest-unit amount into INR.
        """

        try:
            return float(
                amount_in_subunits
            ) / 100
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RazorpayConnectorError(
                f"Invalid Razorpay amount: "
                f"{amount_in_subunits}"
            ) from exc


# ================================================================
# SINGLETON / FACTORY
# ================================================================

_connector: Optional[
    RazorpayConnector
] = None


def get_razorpay_connector() -> RazorpayConnector:
    """
    Return a process-wide Razorpay connector.
    """

    global _connector

    if _connector is None:
        _connector = RazorpayConnector()

    return _connector


def reset_razorpay_connector() -> None:
    """
    Reset the connector.

    Primarily useful for tests when environment variables change.
    """

    global _connector
    _connector = None