from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.models.usage import LlmUsage
from src.services.usage_service import LIMITS, RateLimited, check_and_record
from tests.conftest import compiled_sql

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def counts(*rows):
    """Each exec(...).one() returns the next (count, oldest) row: per-minute,
    per-day, then all-users-per-day."""
    session = MagicMock()
    session.exec.side_effect = [MagicMock(one=MagicMock(return_value=r)) for r in rows]
    return session


UNDER = (0, None)


class TestCheckAndRecord:
    def test_records_the_call_when_under_every_limit(self, user):
        session = counts(UNDER, UNDER, UNDER)

        check_and_record(session, user, "turn", now=NOW)

        (usage,) = session.add.call_args.args
        assert isinstance(usage, LlmUsage)
        assert (usage.user_id, usage.action, usage.created_at) == (1, "turn", NOW)
        session.commit.assert_called_once()

    def test_counts_this_users_calls_of_this_kind(self, user):
        session = counts(UNDER, UNDER, UNDER)

        check_and_record(session, user, "preview", now=NOW)

        minute, day, everyone = (
            compiled_sql(c.args[0]) for c in session.exec.call_args_list
        )
        for sql in (minute, day):
            assert "llmusage.user_id = 1" in sql
            assert "llmusage.action = 'preview'" in sql
        assert "llmusage.created_at >= '2026-11-05 11:59:00+00:00'" in minute
        assert "llmusage.created_at >= '2026-11-04 12:00:00+00:00'" in day
        assert "user_id" not in everyone.split("WHERE")[1]
        assert "llmusage.action = 'preview'" in everyone

    def test_refuses_a_burst_and_says_when_to_retry(self, user):
        per_minute = LIMITS["turn"].per_minute
        session = counts((per_minute, NOW - timedelta(seconds=45)))

        with pytest.raises(RateLimited) as refused:
            check_and_record(session, user, "turn", now=NOW)

        assert refused.value.retry_after == 15
        assert "too fast" in refused.value.message
        session.add.assert_not_called()

    def test_refuses_past_the_daily_limit(self, user):
        per_day = LIMITS["campaign"].per_day
        session = counts(UNDER, (per_day, NOW - timedelta(hours=20)))

        with pytest.raises(RateLimited) as refused:
            check_and_record(session, user, "campaign", now=NOW)

        assert refused.value.retry_after == 4 * 3600
        assert f"{per_day} campaigns" in refused.value.message
        assert "4 hours" in refused.value.message
        session.add.assert_not_called()

    def test_refuses_when_everyone_has_used_todays_budget(self, user):
        everyone = LIMITS["turn"].all_users_per_day
        session = counts(
            UNDER, UNDER, (everyone, NOW - timedelta(hours=23, minutes=30))
        )

        with pytest.raises(RateLimited) as refused:
            check_and_record(session, user, "turn", now=NOW)

        assert refused.value.retry_after == 30 * 60
        assert "everyone" in refused.value.message
        session.add.assert_not_called()

    def test_retry_is_at_least_a_second(self, user):
        session = counts((LIMITS["turn"].per_minute, NOW - timedelta(seconds=60)))

        with pytest.raises(RateLimited) as refused:
            check_and_record(session, user, "turn", now=NOW)

        assert refused.value.retry_after == 1
