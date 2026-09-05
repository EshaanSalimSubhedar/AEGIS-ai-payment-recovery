import re
from datetime import date, datetime, timedelta
from typing import Optional


# ============================================================
# PROMISE-TO-PAY DETECTION
# ============================================================

PTP_PATTERNS = [
    r"\bpay(?:ing)?\b",
    r"\bi['’]ll\s+pay\b",
    r"\bi\s+will\s+pay\b",
    r"\bwill\s+pay\b",
    r"\bpayment\b",
]


# ============================================================
# MONTH NAME MAPPING
# ============================================================

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


# ============================================================
# DATE PARSING
# ============================================================

def parse_promised_date(
    reply: str,
    reference_date: Optional[date] = None,
) -> Optional[date]:
    """
    Extract a promised payment date from a customer reply.

    Supported examples:

        I'll pay tomorrow
        I'll pay today

        I'll pay on 10/09
        I'll pay by 10/09
        I'll pay on 10-09
        I'll pay by 10-09

        I'll pay on September 10
        I'll pay by September 10
        I will pay September 10

        I'll pay on September 10, 2026
        I'll pay by 10 September 2026
    """

    if not reply:
        return None

    text = reply.strip().lower()

    today = reference_date or date.today()

    # --------------------------------------------------------
    # Relative date: tomorrow
    # --------------------------------------------------------

    if re.search(r"\btomorrow\b", text):
        return today + timedelta(days=1)

    # --------------------------------------------------------
    # Relative date: today
    # --------------------------------------------------------

    if re.search(r"\btoday\b", text):
        return today

    # --------------------------------------------------------
    # Numeric dates
    #
    # Examples:
    #   10/09
    #   10-09
    #   10/09/2026
    #   10-09-2026
    # --------------------------------------------------------

    numeric_match = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b",
        text,
    )

    if numeric_match:
        day = int(numeric_match.group(1))
        month = int(numeric_match.group(2))
        year_text = numeric_match.group(3)

        if year_text:
            year = int(year_text)

            # Convert 26 -> 2026
            if year < 100:
                year += 2000
        else:
            year = today.year

        try:
            promised = date(
                year,
                month,
                day,
            )

            # If no year was supplied and the date has
            # already passed this year, assume next year.
            if not year_text and promised < today:
                promised = date(
                    today.year + 1,
                    month,
                    day,
                )

            return promised

        except ValueError:
            return None

    # --------------------------------------------------------
    # Month followed by day
    #
    # Examples:
    #   September 10
    #   September 10, 2026
    # --------------------------------------------------------

    month_names = (
        "january|february|march|april|may|june|"
        "july|august|september|october|november|december"
    )

    month_day_match = re.search(
        rf"\b({month_names})\s+(\d{{1,2}})"
        rf"(?:,\s*(\d{{4}}))?\b",
        text,
    )

    if month_day_match:
        month_name = month_day_match.group(1)
        day = int(month_day_match.group(2))
        year_text = month_day_match.group(3)

        month = MONTHS[month_name]

        if year_text:
            year = int(year_text)
        else:
            year = today.year

        try:
            promised = date(
                year,
                month,
                day,
            )

            # If no year was supplied and the date has
            # already passed this year, assume next year.
            if not year_text and promised < today:
                promised = date(
                    today.year + 1,
                    month,
                    day,
                )

            return promised

        except ValueError:
            return None

    # --------------------------------------------------------
    # Day followed by month
    #
    # Examples:
    #   10 September
    #   10 September 2026
    # --------------------------------------------------------

    day_month_match = re.search(
        rf"\b(\d{{1,2}})\s+({month_names})"
        rf"(?:\s+(\d{{4}}))?\b",
        text,
    )

    if day_month_match:
        day = int(day_month_match.group(1))
        month_name = day_month_match.group(2)
        year_text = day_month_match.group(3)

        month = MONTHS[month_name]

        if year_text:
            year = int(year_text)
        else:
            year = today.year

        try:
            promised = date(
                year,
                month,
                day,
            )

            # If no year was supplied and the date has
            # already passed this year, assume next year.
            if not year_text and promised < today:
                promised = date(
                    today.year + 1,
                    month,
                    day,
                )

            return promised

        except ValueError:
            return None

    # Nothing recognizable was found.
    return None


# ============================================================
# PTP DETECTION
# ============================================================

def detect_promise_to_pay(
    reply: str,
    reference_date: Optional[date] = None,
) -> Optional[date]:
    """
    Detect whether a customer reply contains a
    promise-to-pay and, if so, return the promised date.

    Examples:

        "I'll pay tomorrow"
        "I'll pay on September 10"
        "I'll pay by September 10"
        "I will pay September 10"

    Returns:
        date    -> promised payment date
        None    -> no detectable PTP
    """

    if not reply:
        return None

    normalized = reply.strip().lower()

    # --------------------------------------------------------
    # Check for promise-to-pay language.
    # --------------------------------------------------------

    has_ptp_language = any(
        re.search(
            pattern,
            normalized,
        )
        for pattern in PTP_PATTERNS
    )

    if not has_ptp_language:
        return None

    # --------------------------------------------------------
    # Extract the actual promised date.
    # --------------------------------------------------------

    return parse_promised_date(
        reply=normalized,
        reference_date=reference_date,
    )


# ============================================================
# FOLLOW-UP DECISION
# ============================================================

def should_send_ptp_follow_up(
    promised_date: date,
    follow_up_sent: bool,
    current_date: Optional[date] = None,
) -> bool:
    """
    Determine whether the scheduled PTP follow-up
    should be sent.

    A follow-up is sent only when:

    1. It has not already been sent.
    2. The promised date has arrived or passed.
    """

    if follow_up_sent:
        return False

    today = current_date or date.today()

    return today >= promised_date


# ============================================================
# FOLLOW-UP SCHEDULING
# ============================================================

def ptp_follow_up_datetime(
    promised_date: date,
    hour: int = 9,
) -> datetime:
    """
    Create the datetime at which the PTP follow-up
    should be scheduled.

    Default:
        09:00 on the promised payment date.
    """

    if not 0 <= hour <= 23:
        raise ValueError(
            "Follow-up hour must be between 0 and 23."
        )

    return datetime.combine(
        promised_date,
        datetime.min.time().replace(
            hour=hour,
        ),
    )