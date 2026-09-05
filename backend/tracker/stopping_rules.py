from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_COOLDOWN_HOURS = 2.0


def can_attempt_recovery(
    attempts: int,
    last_attempt_at: Optional[datetime] = None,
    opted_out: bool = False,
    status: Optional[str] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    cooldown_hours: float = DEFAULT_COOLDOWN_HOURS,
    now: Optional[datetime] = None,
) -> bool:
    return get_block_reason(
        attempts=attempts,
        last_attempt_at=last_attempt_at,
        opted_out=opted_out,
        status=status,
        max_attempts=max_attempts,
        cooldown_hours=cooldown_hours,
        now=now,
    ) is None


def can_execute_automated_action(
    attempts: int,
    last_attempt_at: Optional[datetime] = None,
    opted_out: bool = False,
    status: Optional[str] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    cooldown_hours: float = DEFAULT_COOLDOWN_HOURS,
    now: Optional[datetime] = None,
) -> bool:
    return can_attempt_recovery(
        attempts=attempts,
        last_attempt_at=last_attempt_at,
        opted_out=opted_out,
        status=status,
        max_attempts=max_attempts,
        cooldown_hours=cooldown_hours,
        now=now,
    )


def get_block_reason(
    attempts: int,
    last_attempt_at: Optional[datetime] = None,
    opted_out: bool = False,
    status: Optional[str] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    cooldown_hours: float = DEFAULT_COOLDOWN_HOURS,
    now: Optional[datetime] = None,
) -> Optional[str]:
    if opted_out:
        return "Customer opted out."

    if status:
        normalized_status = status.strip().lower()

        if normalized_status == "recovered":
            return "Payment is already recovered."

        if normalized_status == "abandoned":
            return "Payment has been abandoned."

    if attempts >= max_attempts:
        return (
            f"Maximum automated recovery attempts "
            f"({max_attempts}) reached."
        )

    if last_attempt_at is not None:
        current_time = now or datetime.utcnow()

        if last_attempt_at.tzinfo is not None and current_time.tzinfo is None:
            current_time = current_time.replace(
                tzinfo=last_attempt_at.tzinfo
            )

        elapsed = current_time - last_attempt_at
        cooldown = timedelta(hours=cooldown_hours)

        if elapsed < cooldown:
            remaining = cooldown - elapsed
            remaining_hours = remaining.total_seconds() / 3600

            return (
                "Recovery cooldown is still active. "
                f"Approximately {remaining_hours:.2f} hours remain."
            )

    return None


def should_abandon(
    attempts: int,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> bool:
    return attempts >= max_attempts


def is_opted_out(opted_out: bool) -> bool:
    return bool(opted_out)


def cooldown_remaining_hours(
    last_attempt_at: Optional[datetime],
    cooldown_hours: float = DEFAULT_COOLDOWN_HOURS,
    now: Optional[datetime] = None,
) -> float:
    if last_attempt_at is None:
        return 0.0

    current_time = now or datetime.utcnow()

    if last_attempt_at.tzinfo is not None and current_time.tzinfo is None:
        current_time = current_time.replace(
            tzinfo=last_attempt_at.tzinfo
        )

    elapsed = current_time - last_attempt_at
    remaining = timedelta(hours=cooldown_hours) - elapsed

    return max(0.0, remaining.total_seconds() / 3600)


def validate_recovery_attempt(
    attempts: int,
    last_attempt_at: Optional[datetime] = None,
    opted_out: bool = False,
    status: Optional[str] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    cooldown_hours: float = DEFAULT_COOLDOWN_HOURS,
) -> dict:
    reason = get_block_reason(
        attempts=attempts,
        last_attempt_at=last_attempt_at,
        opted_out=opted_out,
        status=status,
        max_attempts=max_attempts,
        cooldown_hours=cooldown_hours,
    )

    return {
        "allowed": reason is None,
        "blocked": reason is not None,
        "reason": reason,
        "attempts": attempts,
        "max_attempts": max_attempts,
        "cooldown_remaining_hours": cooldown_remaining_hours(
            last_attempt_at=last_attempt_at,
            cooldown_hours=cooldown_hours,
        ),
    }