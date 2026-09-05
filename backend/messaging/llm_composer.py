import os
from typing import Optional

from dotenv import load_dotenv
from groq import Groq


load_dotenv()


# ==========================================
# Configuration
# ==========================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

DEFAULT_MODEL = "llama-3.3-70b-versatile"


# ==========================================
# Exceptions
# ==========================================

class LLMComposerError(Exception):
    """
    Raised when the LLM message-generation process fails.
    """


# ==========================================
# Static fallback templates
# ==========================================

FALLBACK_TEMPLATES = {
    "insufficient_funds": (
        "Hi {customer_name}, your recent payment of "
        "₹{amount:.2f} could not be completed due to "
        "insufficient funds. Please check your balance "
        "and try again when convenient."
    ),

    "bank_timeout": (
        "Hi {customer_name}, your recent payment of "
        "₹{amount:.2f} could not be completed because "
        "the bank connection timed out. You can try "
        "the payment again shortly."
    ),

    "card_expired": (
        "Hi {customer_name}, your payment of "
        "₹{amount:.2f} could not be completed because "
        "the card appears to have expired. Please use "
        "an updated payment method to complete your payment."
    ),

    "issuer_declined": (
        "Hi {customer_name}, your recent payment of "
        "₹{amount:.2f} was declined by the card issuer. "
        "Please check with your bank or try another payment method."
    ),

    "network_error": (
        "Hi {customer_name}, your payment of "
        "₹{amount:.2f} could not be completed because "
        "of a temporary network issue. Please try again."
    ),

    "authentication_failed": (
        "Hi {customer_name}, your payment of "
        "₹{amount:.2f} could not be authenticated. "
        "Please try the payment again using the secure payment flow."
    ),

    "limit_exceeded": (
        "Hi {customer_name}, your payment of "
        "₹{amount:.2f} could not be completed because "
        "a transaction limit may have been reached. "
        "Please try another payment method or contact your bank."
    ),

    "fraud_review": (
        "Hi {customer_name}, we were unable to complete "
        "your payment of ₹{amount:.2f}. Please contact "
        "support if you need assistance completing the payment."
    ),

    "unknown": (
        "Hi {customer_name}, we were unable to complete "
        "your recent payment of ₹{amount:.2f}. "
        "Please try again or use another payment method."
    ),
}


# ==========================================
# Prompt builder
# ==========================================

def build_prompt(
    customer_name: str,
    amount: float,
    failure_reason: str,
    action: str,
    language_pref: str = "english",
    payment_link: Optional[str] = None,
) -> str:
    """
    Build the controlled prompt sent to the LLM.

    The LLM is responsible for wording only.

    It must NOT decide:
        - whether to retry
        - how many retries are allowed
        - whether to abandon
        - whether to escalate

    Those decisions are made by the deterministic
    action planner and stopping rules.
    """

    link_instruction = ""

    if payment_link:
        link_instruction = f"""
A payment link is available:
{payment_link}

Include the payment link naturally in the message.
"""

    language_instruction = (
        "Write the message in natural English."
    )

    if language_pref.lower() != "english":
        language_instruction = (
            f"Write the message naturally in "
            f"{language_pref}. Keep it concise and easy to understand."
        )

    return f"""
You are a payment-recovery messaging assistant.

Write ONE short customer-facing recovery message.

Customer name:
{customer_name}

Failed payment amount:
₹{amount:.2f}

Failure reason:
{failure_reason}

Recovery action:
{action}

{language_instruction}

Requirements:
- Be warm, professional, and concise.
- Do not blame or shame the customer.
- Do not invent facts.
- Do not claim that payment was successfully recovered.
- Do not mention internal AI systems.
- Do not mention recovery scores.
- Do not mention internal rules.
- Do not use excessive urgency.
- Do not ask for sensitive banking credentials, PINs, CVVs, or passwords.
- If a payment link is provided, include it.
- Keep the message under 480 characters.
{link_instruction}

Return only the final customer-facing message.
""".strip()


# ==========================================
# Fallback message
# ==========================================

def build_fallback_message(
    customer_name: str,
    amount: float,
    failure_reason: str,
) -> str:
    """
    Generate a deterministic message when the Groq API
    is unavailable.
    """

    template = FALLBACK_TEMPLATES.get(
        failure_reason,
        FALLBACK_TEMPLATES["unknown"],
    )

    return template.format(
        customer_name=customer_name or "Customer",
        amount=amount,
    )


# ==========================================
# LLM composer
# ==========================================

class LLMComposer:
    """
    Groq-powered message composer.

    The composer has an explicit fallback path so an LLM
    outage does not stop payment recovery.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ):
        self.api_key = (
            api_key
            or GROQ_API_KEY
        )

        self.model = model

        self.client = None

        if self.api_key:
            self.client = Groq(
                api_key=self.api_key
            )

    # ======================================
    # Generate message
    # ======================================

    def compose(
        self,
        customer_name: str,
        amount: float,
        failure_reason: str,
        action: str,
        language_pref: str = "english",
        payment_link: Optional[str] = None,
    ) -> tuple[str, bool]:
        """
        Generate a recovery message.

        Returns:

            (message, fallback_used)

        Example:

            (
                "Hi Alex, your payment...",
                False
            )

        or if Groq fails:

            (
                "Hi Alex, your payment...",
                True
            )
        """

        # --------------------------------------
        # No API key
        # --------------------------------------

        if not self.client:
            return (
                build_fallback_message(
                    customer_name=customer_name,
                    amount=amount,
                    failure_reason=failure_reason,
                ),
                True,
            )

        prompt = build_prompt(
            customer_name=customer_name,
            amount=amount,
            failure_reason=failure_reason,
            action=action,
            language_pref=language_pref,
            payment_link=payment_link,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You write concise and safe "
                            "payment recovery messages."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.3,
                max_tokens=180,
            )

            message = (
                response.choices[0]
                .message
                .content
                .strip()
            )

            if not message:
                raise LLMComposerError(
                    "Groq returned an empty message."
                )

            # Enforce the application-level length limit.
            message = message[:480]

            return message, False

        except Exception:
            # Intentionally catch provider errors here.
            #
            # The calling service can then log
            # "llm_fallback_used" in the audit trail.
            return (
                build_fallback_message(
                    customer_name=customer_name,
                    amount=amount,
                    failure_reason=failure_reason,
                ),
                True,
            )


# ==========================================
# Singleton helper
# ==========================================

_composer: Optional[LLMComposer] = None


def get_llm_composer() -> LLMComposer:
    """
    Lazily initialize the LLM composer.
    """

    global _composer

    if _composer is None:
        _composer = LLMComposer()

    return _composer