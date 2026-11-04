"""Limits on requests that call Claude, so one player (or many free Discord accounts)
can't run up the API bill. Each accepted request is recorded in `llmusage`; a request
is refused while a user is over their per-minute or 24-hour limit, or everyone
together is over the 24-hour total for that kind of request."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func
from sqlmodel import Session, col, select

from src.models.usage import LlmUsage
from src.models.user import User

Action = Literal["turn", "preview", "campaign"]


@dataclass(frozen=True)
class Limit:
    noun: str  # plural, for messages
    per_minute: int
    per_day: int  # per user, rolling 24 hours
    all_users_per_day: int  # everyone together, rolling 24 hours


# Tunable. A turn is 1-2 Claude calls plus memory extraction; a campaign is a tool loop.
LIMITS: dict[str, Limit] = {
    "turn": Limit("turns", per_minute=10, per_day=300, all_users_per_day=3000),
    "preview": Limit(
        "character previews", per_minute=5, per_day=30, all_users_per_day=300
    ),
    "campaign": Limit("campaigns", per_minute=2, per_day=10, all_users_per_day=100),
}

MINUTE = timedelta(minutes=1)
DAY = timedelta(days=1)


class RateLimited(Exception):
    def __init__(self, retry_after: int, message: str):
        super().__init__(message)
        self.retry_after = retry_after
        self.message = message


def _window(
    session: Session, action: str, since: datetime, user_id: int | None
) -> tuple[int, datetime | None]:
    """How many recorded calls since `since`, and when the oldest of them was."""
    statement = select(func.count(), func.min(LlmUsage.created_at)).where(
        LlmUsage.action == action, col(LlmUsage.created_at) >= since
    )
    if user_id is not None:
        statement = statement.where(LlmUsage.user_id == user_id)
    count, oldest = session.exec(statement).one()
    return count, oldest


def _retry_after(oldest: datetime | None, window: timedelta, now: datetime) -> int:
    """Seconds until the oldest call in the window ages out of it."""
    if oldest is None:
        return 1
    return max(1, math.ceil((oldest + window - now).total_seconds()))


def _wait(seconds: int) -> str:
    if seconds < 90:
        return f"{seconds} seconds"
    if seconds < 5400:
        return f"{round(seconds / 60)} minutes"
    return f"{round(seconds / 3600)} hours"


def check_and_record(
    session: Session, user: User, action: Action, now: datetime | None = None
) -> None:
    """Record a call to Claude for `user`, or raise RateLimited if it's over a limit.

    Called once a request is known to be valid and before Claude is called. A call
    counts even if Claude then fails, so retrying can't get around the limit."""
    assert user.id is not None
    limit = LIMITS[action]
    now = now or datetime.now(UTC)

    count, oldest = _window(session, action, now - MINUTE, user.id)
    if count >= limit.per_minute:
        wait = _retry_after(oldest, MINUTE, now)
        raise RateLimited(wait, f"You're going too fast. Try again in {_wait(wait)}.")

    count, oldest = _window(session, action, now - DAY, user.id)
    if count >= limit.per_day:
        wait = _retry_after(oldest, DAY, now)
        raise RateLimited(
            wait,
            f"You've reached the limit of {limit.per_day} {limit.noun} a day. "
            f"Try again in {_wait(wait)}.",
        )

    count, oldest = _window(session, action, now - DAY, None)
    if count >= limit.all_users_per_day:
        wait = _retry_after(oldest, DAY, now)
        raise RateLimited(
            wait,
            f"The Dungeon Master is resting: today's {limit.noun} are used up for "
            f"everyone. Try again in {_wait(wait)}.",
        )

    session.add(LlmUsage(user_id=user.id, action=action, created_at=now))
    session.commit()
