"""Cadence rules for the LLM scheduler."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from plastiglom.apps.llm_scheduler.cadence import MonthlyDay, Weekly

UTC = ZoneInfo("UTC")


def test_weekly_previous_tick_returns_most_recent_match() -> None:
    rule = Weekly(weekday=6, at=time(22, 0), tz=UTC)  # Sunday 22:00
    # Wednesday 2026-05-13 12:00 UTC -> prev tick was Sunday 2026-05-10 22:00
    now = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    prev = rule.previous_tick(now)
    assert prev == datetime(2026, 5, 10, 22, 0, tzinfo=UTC)


def test_weekly_previous_tick_before_today_time_skips_back_to_last_week() -> None:
    rule = Weekly(weekday=6, at=time(22, 0), tz=UTC)
    # Sunday morning before 22:00 — last tick was the previous Sunday.
    now = datetime(2026, 5, 10, 8, 0, tzinfo=UTC)
    prev = rule.previous_tick(now)
    assert prev == datetime(2026, 5, 3, 22, 0, tzinfo=UTC)


def test_weekly_previous_tick_on_match_returns_now_if_equal() -> None:
    rule = Weekly(weekday=6, at=time(22, 0), tz=UTC)
    now = datetime(2026, 5, 10, 22, 0, tzinfo=UTC)
    prev = rule.previous_tick(now)
    assert prev == now


def test_weekly_next_tick_is_seven_days_after_prev() -> None:
    rule = Weekly(weekday=6, at=time(22, 0), tz=UTC)
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)
    nxt = rule.next_tick(now)
    assert nxt == datetime(2026, 5, 17, 22, 0, tzinfo=UTC)


def test_weekly_respects_local_timezone_boundaries() -> None:
    tokyo = ZoneInfo("Asia/Tokyo")
    rule = Weekly(weekday=6, at=time(22, 0), tz=tokyo)
    # 2026-05-10 14:00 UTC == 2026-05-10 23:00 Tokyo (Sunday) -> just past tick.
    now = datetime(2026, 5, 10, 14, 0, tzinfo=UTC)
    prev = rule.previous_tick(now)
    assert prev == datetime(2026, 5, 10, 22, 0, tzinfo=tokyo)


def test_weekly_invalid_weekday_raises() -> None:
    with pytest.raises(ValueError):
        Weekly(weekday=7, at=time(0, 0), tz=UTC)


def test_monthly_last_day_resolves_correctly_across_lengths() -> None:
    rule = MonthlyDay(day=-1, at=time(23, 0), tz=UTC)
    # February 2026 has 28 days.
    now = datetime(2026, 2, 15, tzinfo=UTC)
    nxt = rule.next_tick(now)
    assert nxt == datetime(2026, 2, 28, 23, 0, tzinfo=UTC)
    # On the tick itself, previous_tick == now (inclusive).
    on_tick = datetime(2026, 2, 28, 23, 0, tzinfo=UTC)
    assert rule.previous_tick(on_tick) == on_tick


def test_monthly_day_clamps_to_month_length() -> None:
    rule = MonthlyDay(day=31, at=time(4, 0), tz=UTC)
    now = datetime(2026, 2, 1, tzinfo=UTC)
    nxt = rule.next_tick(now)
    assert nxt == datetime(2026, 2, 28, 4, 0, tzinfo=UTC)


def test_monthly_previous_tick_wraps_to_previous_month() -> None:
    rule = MonthlyDay(day=15, at=time(4, 0), tz=UTC)
    now = datetime(2026, 5, 1, tzinfo=UTC)  # before the May tick
    prev = rule.previous_tick(now)
    assert prev == datetime(2026, 4, 15, 4, 0, tzinfo=UTC)


def test_monthly_next_tick_wraps_to_next_year() -> None:
    rule = MonthlyDay(day=-1, at=time(23, 0), tz=UTC)
    now = datetime(2026, 12, 31, 23, 30, tzinfo=UTC)  # just past December tick
    nxt = rule.next_tick(now)
    assert nxt == datetime(2027, 1, 31, 23, 0, tzinfo=UTC)


def test_monthly_invalid_day_raises() -> None:
    with pytest.raises(ValueError):
        MonthlyDay(day=0, at=time(0, 0), tz=UTC)
    with pytest.raises(ValueError):
        MonthlyDay(day=32, at=time(0, 0), tz=UTC)
